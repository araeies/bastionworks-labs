"""Lab 0 practice self-checks. PRACTICE ONLY: not a verification. Prints every az command it runs."""

import json
import shlex
import subprocess
import sys

EXPECTED_ASSIGNMENTS = ["bw-allowed-locations", "bw-allowed-vm-sizes", "bw-denied-resource-types"]


def az(*args):
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors", "-o", "json"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False)
    if done.returncode != 0:
        print(f"  az failed: {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else done.returncode}")
        return None
    return json.loads(done.stdout) if done.stdout.strip() else None


def main():
    results = []
    account = az("account", "show")
    if not account:
        print("Not signed in. Run: az login")
        return 1
    tags = ((az("tag", "list", "--resource-id", f"/subscriptions/{account['id']}") or {}).get("properties") or {}).get("tags") or {}
    results.append(("Playground tag set", str(tags.get("bastionworks:playground", "")).lower() == "true"))
    budgets = az("consumption", "budget", "list") or []
    results.append(("Lab 0 budget exists", any(str(b.get("name", "")).startswith("bw-lab-0-budget-") for b in budgets)))
    names = {a.get("name") for a in az("policy", "assignment", "list") or []}
    for expected in EXPECTED_ASSIGNMENTS:
        results.append((f"Policy assignment {expected}", expected in names))

    print()
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print("\nThese checks only look at your subscription. The checkpoint verifies the guardrails in YOUR repo.")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
