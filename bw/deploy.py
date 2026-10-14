"""bw deploy <lab> --seed <code>: deploy a kit into its own tagged resource group (brief §4.1).

Lab 0 (scope "subscription") is the only kit allowed before the playground tag exists, because it is
the lab that creates the tag, budget and guardrails. It requires typing the subscription's exact name.
"""

import json
import os
import shlex
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, TextIO

from bw.az import Az
from bw.conventions import EXPIRES_TAG, KIT_TAG, LAB_TAG, SEED_TAG, resource_group_name
from bw.doctor import print_report, run_doctor
from labspec import derive_name, load_manifest, normalise_seed

DEFAULT_EXPIRY_DAYS = 2


class DeployError(Exception):
    pass


def derived_names(manifest, seed: str) -> Dict[str, str]:
    names = {}
    for key, spec in manifest.kit["names"].items():
        names[key] = derive_name(manifest.id, seed, key, spec["prefix"], spec["length"], spec.get("alphabet", "lower-alnum"))
    return names


def _run_seed_script(script: Path, env_extra: Dict[str, str], out: TextIO) -> None:
    print("$ " + " ".join(f"{k}={shlex.quote(v)}" for k, v in sorted(env_extra.items())) + f" bash {shlex.quote(str(script))}",
          file=out, flush=True)
    completed = subprocess.run(["bash", str(script)], env={**os.environ, **env_extra}, check=False)
    if completed.returncode != 0:
        raise DeployError(f"seed script exited with status {completed.returncode}")


def run_deploy(az: Az, lab_id: str, seed: str, kit_dir: Path, region: str, out: TextIO,
               confirm: Callable[[str], str], assume_yes: bool = False, today: date = None,
               expiry_days: int = DEFAULT_EXPIRY_DAYS) -> int:
    today = today or date.today()
    manifest = load_manifest(kit_dir)
    if manifest.id != lab_id:
        raise DeployError(f"kit is for '{manifest.id}', not '{lab_id}'")
    seed = normalise_seed(seed)
    names = derived_names(manifest, seed)
    kit = manifest.kit
    template = manifest.path(kit["template"])
    expires = (today + timedelta(days=expiry_days)).isoformat()
    params = [f"labId={manifest.id}", f"seed={seed}", f"names={json.dumps(names, sort_keys=True)}", f"expires={expires}"]

    if kit["scope"] == "subscription":
        account = az.run(["account", "show"])
        print(f"\n{manifest.data['title']} ({manifest.id}@{manifest.version})", file=out)
        print(f"This turns subscription '{account['name']}' ({account['id']}) into your Bastionworks playground:", file=out)
        print("  budget alerts, guardrail policies, and the bastionworks:playground tag.", file=out)
        print("  Use a DEDICATED subscription. Never a work, production or shared one.", file=out)
        print(f"  Estimated cost: ${manifest.data['learnerCostEstimateUsd']:.2f}", file=out)
        if not assume_yes and not az.dry_run:
            if confirm(f"\nType the subscription name ({account['name']}) to confirm: ").strip() != account["name"]:
                print("Not confirmed. Nothing was deployed.", file=out)
                return 1
        az.run(["deployment", "sub", "create", "--location", region, "--name", f"bw-{manifest.id}",
                "--template-file", str(template), "--parameters", *params], mutating=True)
        print("\nDone. Now run: bw doctor", file=out)
        return 0

    report = run_doctor(az, region)
    if not report.ok:
        print_report(report, out)
        return 1
    group = resource_group_name(manifest.id, seed)
    print(f"\n{manifest.data['title']} ({manifest.id}@{manifest.version})", file=out)
    print(f"  Subscription:  {report.subscription['name']}", file=out)
    print(f"  Resource group: {group} ({region}), expires {expires}", file=out)
    print(f"  Estimated cost: ${manifest.data['learnerCostEstimateUsd']:.2f} for about {manifest.data['estimatedMinutes']} minutes", file=out)
    print("  Deliberately vulnerable resources hold synthetic data only. Run `bw cleanup` when you have verified.", file=out)
    if not assume_yes and not az.dry_run:
        if confirm("\nType 'deploy' to continue: ").strip() != "deploy":
            print("Not confirmed. Nothing was deployed.", file=out)
            return 1

    tags = [f"{LAB_TAG}={manifest.id}", f"{SEED_TAG}={seed}", f"{KIT_TAG}={manifest.id}@{manifest.version}", f"{EXPIRES_TAG}={expires}"]
    az.run(["group", "create", "--name", group, "--location", region, "--tags", *tags], mutating=True)
    az.run(["deployment", "group", "create", "--resource-group", group, "--name", f"bw-{manifest.id}",
            "--template-file", str(template), "--parameters", *params], mutating=True)

    if "seed" in kit:
        env = {"BW_LAB": manifest.id, "BW_SEED": seed, "BW_RESOURCE_GROUP": group,
               **{f"BW_NAME_{k.upper()}": v for k, v in names.items()}}
        if az.dry_run:
            print(f"(dry run: seed script {kit['seed']} not executed)", file=out)
        else:
            _run_seed_script(manifest.path(kit["seed"]), env, out)

    print("\nDeployed. Next:", file=out)
    print(f"  bw check {manifest.id}     practice self-checks (not a verification)", file=out)
    print(f"  bw hint {manifest.id} 1    if you are stuck", file=out)
    print(f"  bw cleanup {manifest.id}   when the platform has verified your work", file=out)
    return 0
