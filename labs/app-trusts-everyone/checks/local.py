"""Lab 2 practice self-checks. PRACTICE ONLY: not a verification. Prints every request and command it makes.

Finds your two apps with az, then makes the same kinds of requests the platform's checks make, from here.
"""

import json
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

GROUP_PREFIX = "rg-bw-app-trusts-everyone-"
HOSTILE = "https://evil.example"


def az(*args):
    print("$ " + " ".join(shlex.quote(a) for a in ("az", *args)), flush=True)
    done = subprocess.run(["az", *args, "--only-show-errors", "-o", "json"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False)
    if done.returncode != 0:
        return None
    return json.loads(done.stdout) if done.stdout.strip() else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # report the redirect instead of following it
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def get(url, origin=None):
    """(status, headers, body) for one GET, without following redirects; status None if unreachable."""
    print(f"$ curl -si{' -H ' + shlex.quote('Origin: ' + origin) if origin else ''} {shlex.quote(url)}", flush=True)
    request = urllib.request.Request(url, headers={"Origin": origin} if origin else {})
    try:
        with _OPENER.open(request, timeout=15) as response:  # nosec: the learner's own lab endpoints
            return response.status, response.headers, response.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read(65536).decode("utf-8", "replace")
    except OSError:
        return None, {}, ""


def cors_denied(headers):
    allowed = (headers.get("Access-Control-Allow-Origin") or "").strip()
    return allowed not in ("*", HOSTILE)


def main():
    groups = [g for g in az("group", "list") or [] if g["name"].startswith(GROUP_PREFIX)]
    if not groups:
        print("No app-trusts-everyone lab found. Deploy it first: bw deploy app-trusts-everyone --seed <code> …")
        return 1
    sites = az("webapp", "list", "--resource-group", groups[0]["name"]) or []
    portal = next((s["defaultHostName"] for s in sites if s["name"].startswith("bw-portal-")), None)
    api = next((s["defaultHostName"] for s in sites if s["name"].startswith("bw-api-")), None)
    if not portal or not api:
        print("Couldn't find both apps (bw-portal-…, bw-api-…) in your lab group.")
        return 1

    results = []
    status, headers, _ = get(f"http://{portal}/")
    location = headers.get("Location") or ""
    results.append((f"Portal: http:// redirects permanently to https:// (got {status})",
                    status in (301, 308) and location.startswith(f"https://{portal}/")))
    status, headers, _ = get(f"https://{portal}/", origin=HOSTILE)
    results.append((f"Portal: home page still answers over HTTPS (got {status})", status == 200))
    results.append(("Portal: a hostile origin isn't granted CORS", cors_denied(headers)))
    wanted = {"Strict-Transport-Security": r"max-age=[1-9][0-9]*", "X-Content-Type-Options": r"^nosniff$",
              "Content-Security-Policy": r"frame-ancestors"}
    for name, pattern in wanted.items():
        results.append((f"Portal: sends {name}", re.search(pattern, headers.get(name) or "") is not None))
    status, _, _ = get(f"https://{portal}/debug/config")
    results.append((f"Portal: debug page is gone (got {status})", status == 404))

    status, headers, body = get(f"https://{api}/api/orders/1", origin=HOSTILE)
    results.append((f"API: anonymous order request refused with 401 (got {status})", status == 401 and "ownerId" not in body))
    results.append(("API: a hostile origin isn't granted CORS", cors_denied(headers)))
    status, headers, _ = get(f"https://{api}/.auth/login/aad")
    results.append((f"API: Entra sign-in endpoint is live (got {status})",
                    status == 302 and (headers.get("Location") or "").startswith("https://login.microsoftonline.com/")))

    print()
    for label, ok in results:
        print(f"  [{'PASS' if ok else 'TODO'}] {label}")
    print("\n  [INFO] The order-ownership fix can't be checked from outside: sign in and confirm you can read")
    print("         orders 1 and 2 (yours, via BW_DEMO_OWNER_OID) but not 3.")
    print("\nPractice only: submit on the lab page for the real checks.")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
