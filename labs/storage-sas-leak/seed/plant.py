"""Plant the lab 1 scenario in the learner's OWN storage account (run by `bw deploy`).

Creates, all with synthetic data:
  - customer-exports/exports/2026-10/customers.csv  (fake rows, @example.invalid addresses)
  - customer-exports/status/healthcheck.txt         (seed-derived token, used by the account-alive checkpoint)
  - a read+list SAS for customer-exports, signed with storage key 1, valid until 30 days after the lab expiry
  - build-artifacts/pipeline-logs/build-1842.log    (a fake CI log that leaks that SAS URL)

Every az command is printed before it runs. The account key is passed via the AZURE_STORAGE_KEY environment
variable, never on the command line or in output.
"""

import os
import shlex
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from labspec import derive_token

LAB = os.environ["BW_LAB"]
SEED = os.environ["BW_SEED"]
GROUP = os.environ["BW_RESOURCE_GROUP"]
ACCOUNT = os.environ["BW_NAME_STORAGEACCOUNT"]
EXPIRES = date.fromisoformat(os.environ["BW_EXPIRES"])


def az(*args: str, env=None) -> str:
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors"], stdout=subprocess.PIPE, text=True,
                          env=env, check=False)
    if done.returncode != 0:
        sys.exit(f"seed failed at: az {' '.join(args[:3])}")
    return done.stdout.strip()


def main() -> int:
    key = az("storage", "account", "keys", "list", "--resource-group", GROUP, "--account-name", ACCOUNT,
             "--query", "[?keyName=='key1'].value | [0]", "-o", "tsv")
    env = {**os.environ, "AZURE_STORAGE_ACCOUNT": ACCOUNT, "AZURE_STORAGE_KEY": key}
    print("  (storage key 1 passed to the next commands via AZURE_STORAGE_KEY, not shown)")

    marker = derive_token(LAB, SEED, "exportMarker")
    health = derive_token(LAB, SEED, "healthToken")
    sas_expiry = (EXPIRES + timedelta(days=30)).isoformat() + "T00:00Z"

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        rows = ["customer_id,name,email,plan,export_marker"]
        rows += [f"SYN-{i:04d},Synthetic Customer {i:03d},customer{i:03d}@example.invalid,standard,{marker}" for i in range(1, 26)]
        (work / "customers.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        (work / "healthcheck.txt").write_text(f"bastionworks-health {health}\n", encoding="utf-8")

        az("storage", "blob", "upload", "--container-name", "customer-exports", "--name", "exports/2026-10/customers.csv",
           "--file", str(work / "customers.csv"), "--overwrite", "--auth-mode", "key", env=env)
        az("storage", "blob", "upload", "--container-name", "customer-exports", "--name", "status/healthcheck.txt",
           "--file", str(work / "healthcheck.txt"), "--overwrite", "--auth-mode", "key", env=env)

        sas = az("storage", "container", "generate-sas", "--name", "customer-exports", "--permissions", "rl",
                 "--expiry", sas_expiry, "--https-only", "--auth-mode", "key", "-o", "tsv", env=env)
        export_url = f"https://{ACCOUNT}.blob.core.windows.net/customer-exports?{sas}"

        log = f"""2026-10-02T09:14:07Z [ci] Pipeline 'nightly-customer-export' run #1842 started (branch: main)
2026-10-02T09:14:09Z [ci] Restoring packages... done
2026-10-02T09:14:31Z [ci] Running export job
2026-10-02T09:14:31Z [debug] EXPORT_TARGET_URL={export_url}
2026-10-02T09:14:58Z [ci] Exported 25 rows to customer-exports/exports/2026-10/customers.csv
2026-10-02T09:15:02Z [ci] Publishing build artifacts to build-artifacts/
2026-10-02T09:15:04Z [ci] Pipeline finished: SUCCESS
"""
        (work / "build-1842.log").write_text(log, encoding="utf-8")
        az("storage", "blob", "upload", "--container-name", "build-artifacts", "--name", "pipeline-logs/build-1842.log",
           "--file", str(work / "build-1842.log"), "--overwrite", "--auth-mode", "key", env=env)

    print("\nScenario planted. Your ticket starts with this public URL:")
    print(f"  https://{ACCOUNT}.blob.core.windows.net/build-artifacts/pipeline-logs/build-1842.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
