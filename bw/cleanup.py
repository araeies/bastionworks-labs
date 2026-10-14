"""bw cleanup <lab>: remove everything a lab created, then prove nothing tagged for it remains (brief §4.1).

Works from a fresh Cloud Shell session with no local state: everything is found by tag or owner marker
(ADR-0014), never from a state file.
"""

import json
from typing import Any, Callable, Dict, List, NamedTuple, TextIO

from bw.az import Az
from bw.conventions import LAB_TAG, PLAYGROUND_LAB, PLAYGROUND_TAG, owner_marker


class CleanupPlan(NamedTuple):
    resource_groups: List[str]
    role_assignments: List[Dict[str, Any]]
    policy_assignments: List[Dict[str, Any]]
    entra_apps: List[Dict[str, Any]]
    budgets: List[str]
    remove_playground_tag: bool

    @property
    def empty(self) -> bool:
        return not (self.resource_groups or self.role_assignments or self.policy_assignments or self.entra_apps
                    or self.budgets or self.remove_playground_tag)


def _tag_filter(lab_id: str) -> str:
    return f"{LAB_TAG}={lab_id}"


def _owned_role_assignments(az: Az, lab_id: str) -> List[Dict[str, Any]]:
    marker = owner_marker(lab_id) + ":"
    assignments = az.run(["role", "assignment", "list", "--all"]) or []
    return [a for a in assignments if str(a.get("description") or "").startswith(marker)]


def _owned_policy_assignments(az: Az, lab_id: str) -> List[Dict[str, Any]]:
    assignments = az.run(["policy", "assignment", "list", "--disable-scope-strict-match"]) or []
    return [a for a in assignments if (a.get("metadata") or {}).get("bastionworksLab") == lab_id]


def _owned_entra_apps(az: Az, lab_id: str) -> List[Dict[str, Any]]:
    tag = owner_marker(lab_id).replace("'", "''")
    return az.run(["ad", "app", "list", "--filter", f"tags/any(t:t eq '{tag}')"]) or []


def _owned_budgets(az: Az, lab_id: str) -> List[str]:
    prefix = f"bw-{lab_id}-budget-"
    return sorted(b["name"] for b in az.run(["consumption", "budget", "list"]) or [] if str(b.get("name", "")).startswith(prefix))


def _playground_tagged(az: Az, lab_id: str) -> bool:
    if lab_id != PLAYGROUND_LAB:
        return False
    sub_id = az.run(["account", "show"])["id"]
    tags = (az.run(["tag", "list", "--resource-id", f"/subscriptions/{sub_id}"]) or {}).get("properties", {}).get("tags") or {}
    return PLAYGROUND_TAG in tags


def _deleted_vaults(az: Az, lab_id: str) -> List[Dict[str, Any]]:
    vaults = az.run(["keyvault", "list-deleted", "--resource-type", "vault"]) or []
    return [v for v in vaults if ((v.get("properties") or {}).get("tags") or {}).get(LAB_TAG) == lab_id]


def plan_cleanup(az: Az, lab_id: str) -> CleanupPlan:
    groups = az.run(["group", "list", "--tag", _tag_filter(lab_id)]) or []
    return CleanupPlan(
        resource_groups=sorted(g["name"] for g in groups),
        role_assignments=_owned_role_assignments(az, lab_id),
        policy_assignments=_owned_policy_assignments(az, lab_id),
        entra_apps=_owned_entra_apps(az, lab_id),
        budgets=_owned_budgets(az, lab_id),
        remove_playground_tag=_playground_tagged(az, lab_id),
    )


def leftovers(az: Az, lab_id: str) -> List[str]:
    """Everything still attributable to the lab. Empty list = clean."""
    found: List[str] = []
    found += [f"resource group {g['name']}" for g in az.run(["group", "list", "--tag", _tag_filter(lab_id)]) or []]
    found += [f"resource {r['id']}" for r in az.run(["resource", "list", "--tag", _tag_filter(lab_id)]) or []]
    found += [f"role assignment {a['id']}" for a in _owned_role_assignments(az, lab_id)]
    found += [f"policy assignment {a['id']}" for a in _owned_policy_assignments(az, lab_id)]
    found += [f"Entra app {a.get('displayName')} ({a.get('appId')})" for a in _owned_entra_apps(az, lab_id)]
    found += [f"soft-deleted Key Vault {v['name']}" for v in _deleted_vaults(az, lab_id)]
    found += [f"budget {b}" for b in _owned_budgets(az, lab_id)]
    if _playground_tagged(az, lab_id):
        found.append(f"subscription tag {PLAYGROUND_TAG}")
    return found


def run_cleanup(az: Az, lab_id: str, out: TextIO, confirm: Callable[[str], str], assume_yes: bool = False) -> int:
    plan = plan_cleanup(az, lab_id)
    vaults = _deleted_vaults(az, lab_id)
    if plan.empty and not vaults:
        print(f"\nNothing tagged for lab '{lab_id}' was found. Checking for leftovers anyway…", file=out)
    else:
        print(f"\nbw cleanup will permanently delete, for lab '{lab_id}':", file=out)
        for name in plan.resource_groups:
            print(f"  - resource group {name} (and everything in it)", file=out)
        for item in plan.role_assignments:
            print(f"  - role assignment {item.get('roleDefinitionName')} → {item.get('principalName') or item.get('principalId')} at {item.get('scope')}", file=out)
        for item in plan.policy_assignments:
            print(f"  - policy assignment {item.get('name')} at {item.get('scope')}", file=out)
        for item in plan.entra_apps:
            print(f"  - Entra app registration {item.get('displayName')} ({item.get('appId')})", file=out)
        for name in plan.budgets:
            print(f"  - budget {name}", file=out)
        if plan.remove_playground_tag:
            print(f"  - the {PLAYGROUND_TAG} subscription tag (bw will refuse to deploy labs here afterwards)", file=out)
        for vault in vaults:
            print(f"  - soft-deleted Key Vault {vault['name']} (purged)", file=out)
        if not assume_yes and az.dry_run is False:
            answer = confirm(f"\nType the lab id ({lab_id}) to confirm: ")
            if answer.strip() != lab_id:
                print("Not confirmed. Nothing was deleted.", file=out)
                return 1

    # Out-of-group objects first: subscription-scoped role assignments survive resource group deletion.
    for item in plan.role_assignments:
        az.run(["role", "assignment", "delete", "--ids", item["id"]], mutating=True)
    for item in plan.policy_assignments:
        az.run(["policy", "assignment", "delete", "--name", item["name"], "--scope", item["scope"]], mutating=True)
    for item in plan.entra_apps:
        az.run(["ad", "app", "delete", "--id", item["appId"]], mutating=True)
    for name in plan.resource_groups:
        az.run(["group", "delete", "--name", name, "--yes"], mutating=True)
    for name in plan.budgets:
        az.run(["consumption", "budget", "delete", "--budget-name", name], mutating=True)
    if plan.remove_playground_tag:
        sub_id = az.run(["account", "show"])["id"]
        az.run(["tag", "update", "--resource-id", f"/subscriptions/{sub_id}", "--operation", "Delete",
                "--tags", f"{PLAYGROUND_TAG}=true"], mutating=True)
    for vault in vaults:
        az.run(["keyvault", "purge", "--name", vault["name"], "--location", vault["properties"]["location"]], mutating=True)

    if az.dry_run:
        print("\nDry run complete: nothing was deleted.", file=out)
        return 0

    remaining = leftovers(az, lab_id)
    if remaining:
        print(f"\nLEFTOVERS: {len(remaining)} item(s) for lab '{lab_id}' still exist:", file=out)
        for item in remaining:
            print(f"  - {item}", file=out)
        print("Run `bw cleanup` again, or remove them by hand. They may still be costing money.", file=out)
        return 1
    print(f"\nClean: nothing tagged for lab '{lab_id}' remains in this subscription.", file=out)
    return 0


def plan_as_json(plan: CleanupPlan) -> str:
    return json.dumps(plan._asdict(), indent=2, sort_keys=True)
