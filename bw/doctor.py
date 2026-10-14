"""bw doctor: pre-flight checks. Refuses to continue if any check fails (brief §4.1)."""

from typing import Any, Dict, List, NamedTuple, Optional, TextIO

from bw.az import Az, AzError, AzNotFound
from bw.conventions import PLAYGROUND_TAG

ALLOWED_LOCATIONS_ASSIGNMENT = "bw-allowed-locations"  # created by Lab 0's guardrail kit


class Check(NamedTuple):
    name: str
    ok: bool
    detail: str


class DoctorReport(NamedTuple):
    checks: List[Check]
    subscription: Optional[Dict[str, Any]]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def _allowed_locations(assignments: List[Dict[str, Any]]) -> Optional[List[str]]:
    for assignment in assignments or []:
        if assignment.get("name") == ALLOWED_LOCATIONS_ASSIGNMENT:
            params = assignment.get("parameters") or {}
            value = (params.get("listOfAllowedLocations") or {}).get("value")
            return [str(v).lower() for v in value] if isinstance(value, list) else None
    return None


def run_doctor(az: Az, region: str) -> DoctorReport:
    checks: List[Check] = []
    region = region.lower()

    try:
        az.run(["version"])
        checks.append(Check("Azure CLI installed", True, "az found"))
    except AzNotFound as error:
        return DoctorReport([Check("Azure CLI installed", False, str(error))], None)

    try:
        account = az.run(["account", "show"])
    except AzError:
        checks.append(Check("Signed in", False, "Not signed in. Run: az login"))
        return DoctorReport(checks, None)
    sub_id = account["id"]
    checks.append(Check("Signed in", True, f"{account.get('user', {}).get('name', '?')} → {account['name']} ({sub_id})"))

    tags = (az.run(["tag", "list", "--resource-id", f"/subscriptions/{sub_id}"]) or {}).get("properties", {}).get("tags") or {}
    tagged = str(tags.get(PLAYGROUND_TAG, "")).lower() == "true"
    checks.append(
        Check(
            "Playground tag",
            tagged,
            f"{PLAYGROUND_TAG}=true present" if tagged
            else f"Subscription is not tagged {PLAYGROUND_TAG}=true. Complete Lab 0 in a DEDICATED subscription; never use a work subscription.",
        )
    )

    budgets = az.run(["consumption", "budget", "list"]) or []
    checks.append(
        Check(
            "Budget alert",
            bool(budgets),
            f"{len(budgets)} budget(s) found" if budgets else "No budget on this subscription. Lab 0 creates one with low alert thresholds.",
        )
    )

    assignments = az.run(["policy", "assignment", "list", "--disable-scope-strict-match"]) or []
    allowed = _allowed_locations(assignments)
    if allowed is None:
        checks.append(Check("Region allowed", False, f"Guardrail policy '{ALLOWED_LOCATIONS_ASSIGNMENT}' not found. Lab 0 deploys it."))
    else:
        checks.append(
            Check(
                "Region allowed",
                region in allowed,
                f"{region} is allowed" if region in allowed else f"{region} is not in the allowed regions {allowed}",
            )
        )
    return DoctorReport(checks, account)


def print_report(report: DoctorReport, out: TextIO) -> None:
    print("", file=out)
    for check in report.checks:
        mark = "PASS" if check.ok else "FAIL"
        print(f"  [{mark}] {check.name}: {check.detail}", file=out)
    print("", file=out)
    print("All checks passed." if report.ok else "bw doctor failed: fix the items above before deploying anything.", file=out)
