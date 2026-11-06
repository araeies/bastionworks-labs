"""Lab 3 practice self-check. PRACTICE ONLY: not a verification. Prints every command it runs.

Runs YOUR rule against the published practice data (data/practice.kql), in YOUR OWN Log Analytics workspace (any
free one: the data travels inside the query, so nothing is ingested). Then it scores it the way the platform scores
the hidden data: by account, as counts only. Passing here doesn't mean passing there, because the hidden data is a
different variant, with its own noise.

  BW_RULE=detections/password-spray.kql bw check password-spray --kit-dir <labs repo>/labs/password-spray

Optional: BW_WORKSPACE=<workspace ID (a GUID)>. Without it, your only workspace is used. If you have several, it
asks you to choose.
"""

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
# The practice data's ground truth, as SHA-256 hashes of the compromised accounts' UserPrincipalName values: enough
# to count how many you caught, without naming them. Practice data only; the hidden variants are different.
PRACTICE_COMPROMISED = {
    "4980779723ecbb13dbd3fea5088cd25601369dd981b68e5433c01b905baeadcb",
    "82964d27dd4359f6e97ee8950d2847e64a7d7a6c6bf361ff401d07bd6d7eb142",
    "834853f42edf0c6dfe65c60e27de528193446f55dc48eba56a555eb877b5088f",
}
MAX_FALSE_ALARMS = 2  # the same pass mark as the real check
MAX_RULE_BYTES = 8 * 1024


def az(*args):
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors", "-o", "json"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False)
    if done.returncode != 0:
        print(done.stderr.strip()[:500])
        return None
    return json.loads(done.stdout) if done.stdout.strip() else None


def practice_prefix():
    """data/practice.kql without its last two lines (`SigninLogs | take 10`), so your rule follows the data."""
    lines = (HERE / "data" / "practice.kql").read_text(encoding="utf-8").rstrip().splitlines()
    return "\n".join(lines[:-2]) + "\n"


def score(upns):
    """(caught, attacked, false_alarms) for the accounts your rule flagged."""
    flagged = {hashlib.sha256(u.encode("utf-8")).hexdigest() for u in upns if isinstance(u, str) and u}
    return len(flagged & PRACTICE_COMPROMISED), len(PRACTICE_COMPROMISED), len(flagged - PRACTICE_COMPROMISED)


def find_workspace():
    chosen = os.environ.get("BW_WORKSPACE", "").strip()
    if chosen:
        return chosen
    found = az("resource", "list", "--resource-type", "Microsoft.OperationalInsights/workspaces",
               "--query", "[].id") or []
    if len(found) != 1:
        print(f"Found {len(found)} Log Analytics workspaces. Set BW_WORKSPACE to the one to use (its Workspace ID,"
              " shown on its Overview page), or create a free one first.")
        return None
    details = az("resource", "show", "--ids", found[0], "--query", "properties.customerId")
    return details if isinstance(details, str) else None


def main():
    rule_path = os.environ.get("BW_RULE", "").strip()
    if not rule_path:
        print("Set BW_RULE to your rule file, for example:\n"
              "  BW_RULE=detections/password-spray.kql bw check password-spray --kit-dir <labs repo>/labs/password-spray")
        return 1
    rule = Path(rule_path).expanduser().read_text(encoding="utf-8").strip()
    if len(rule.encode("utf-8")) > MAX_RULE_BYTES:
        print("Your rule is over 8 KiB; the real check refuses rules that size.")
        return 1
    if "datatable(" in rule or "let SigninLogs" in rule:
        print("Commit just the rule, starting from SigninLogs, without the practice data (the check adds it).")
        return 1
    workspace = find_workspace()
    if not workspace:
        return 1

    body = json.dumps({"query": practice_prefix() + rule})
    print("  (your rule runs after the practice data; nothing is ingested)")
    result = az("rest", "--method", "post", "--url", f"https://api.loganalytics.io/v1/workspaces/{workspace}/query",
                "--resource", "https://api.loganalytics.io", "--headers", "Content-Type=application/json", "--body", body)
    if not result or not result.get("tables"):
        print("The query didn't run. Fix any error above (try your rule in the workspace's Logs page), then retry.")
        return 1
    table = result["tables"][0]
    names = [c["name"] for c in table["columns"]]
    if "UserPrincipalName" not in names:
        print(f"Your rule must return a UserPrincipalName column; it returned: {', '.join(names) or 'no columns'}.")
        return 1
    column = names.index("UserPrincipalName")
    caught, attacked, false_alarms = score(row[column] for row in table["rows"])

    print()
    print(f"  [{'PASS' if caught == attacked else 'TODO'}] Caught {caught} of {attacked} compromised accounts")
    print(f"  [{'PASS' if false_alarms <= MAX_FALSE_ALARMS else 'TODO'}] {false_alarms} false alarm"
          f"{'s' if false_alarms != 1 else ''} (at most {MAX_FALSE_ALARMS})")
    print("\nPractice only: the real check runs your committed rule against unseen data. Submit on the lab page.")
    return 0 if caught == attacked and false_alarms <= MAX_FALSE_ALARMS else 1


if __name__ == "__main__":
    sys.exit(main())
