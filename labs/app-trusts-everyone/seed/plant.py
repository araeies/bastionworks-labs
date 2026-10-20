"""Plant the lab 2 scenario: deploy the deliberately vulnerable app code to the learner's OWN two apps (run by `bw deploy`).

The infrastructure (plan, apps, their settings) comes from infra/main.bicep. This script zips ../app (Node.js
built-ins only, no dependencies) and deploys it to both apps with `az webapp deploy`. The app derives its
seed-based values itself (app/derive.js), so nothing secret is planted. Every az command is printed before it runs.
"""

import os
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

GROUP = os.environ["BW_RESOURCE_GROUP"]
PORTAL = os.environ["BW_NAME_PORTAL"]
API = os.environ["BW_NAME_API"]
APP_DIR = Path(__file__).resolve().parent.parent / "app"


def az(*args: str) -> None:
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors", "-o", "none"], check=False)
    if done.returncode != 0:
        sys.exit(f"seed failed at: az {' '.join(args[:3])}")


def build_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(APP_DIR.iterdir()):
            if path.is_file():
                archive.write(path, path.name)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "app.zip"
        build_zip(package)
        for app in (PORTAL, API):
            az("webapp", "deploy", "--resource-group", GROUP, "--name", app, "--src-path", str(package), "--type", "zip")

    print("\nScenario planted. Your ticket covers these two apps:")
    print(f"  portal      http://{PORTAL}.azurewebsites.net/")
    print(f"  orders API  http://{API}.azurewebsites.net/api/orders/1")
    print("The app code is in the kit's app/ folder: fork it into your own repo to fix it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
