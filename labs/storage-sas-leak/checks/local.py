"""Lab 1 practice self-checks. PRACTICE ONLY: not a verification. Prints every command it runs.

Reads your lab storage account's settings with az, and tries the build log anonymously.
"""

import json
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

GROUP_PREFIX = "rg-bw-storage-sas-leak-"


def az(*args):
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors", "-o", "json"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False)
    if done.returncode != 0:
        return None
    return json.loads(done.stdout) if done.stdout.strip() else None


def anonymous_status(url):
    print(f"$ curl -s -o /dev/null -w '%{{http_code}}' {shlex.quote(url)}", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # nosec: the learner's own lab endpoint
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except OSError:
        return None


def main():
    groups = [g for g in az("group", "list") or [] if g["name"].startswith(GROUP_PREFIX)]
    if not groups:
        print("No storage-sas-leak lab found. Deploy it first: bw deploy storage-sas-leak --seed <code> …")
        return 1
    group = groups[0]["name"]
    accounts = az("storage", "account", "list", "--resource-group", group) or []
    if not accounts:
        print(f"No storage account in {group}.")
        return 1
    account = accounts[0]
    name = account["name"]
    status = anonymous_status(f"https://{name}.blob.core.windows.net/build-artifacts/pipeline-logs/build-1842.log")

    results = [
        ("Account-level anonymous access disabled (allowBlobPublicAccess = false)", account.get("allowBlobPublicAccess") is False),
        ("Shared-key access disabled (allowSharedKeyAccess = false)", account.get("allowSharedKeyAccess") is False),
        (f"Build log not readable anonymously (got HTTP {status})", status in (404, 409)),
    ]
    print()
    for label, ok in results:
        print(f"  [{'PASS' if ok else 'TODO'}] {label}")
    print("\nDisabling shared-key access is one way to kill the leaked SAS; rotating key 1 is another.")
    print("These checks can't see which you chose. The leak-dead checkpoint tests the token itself.")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
