"""Lab 2's app (labs/app-trusts-everyone/app): the JavaScript seed derivation matches labspec's, and the app ships
with exactly the weaknesses the scenario describes. Runs the real app with Node.js; skipped where Node isn't installed."""

import json
import os
import shutil
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from labspec import derive_token
from labspec.knowledge import expected_token

APP = Path(__file__).resolve().parent.parent / "labs" / "app-trusts-everyone" / "app"
LAB, SEED = "app-trusts-everyone", "K7Q2MX4P"
NODE = shutil.which("node")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port, path, headers=None):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode()


@unittest.skipUnless(NODE, "node is not installed")
class Lab2AppTest(unittest.TestCase):
    def test_javascript_derivation_matches_labspec(self):
        script = ("const d = require(process.argv[1]);"
                  "console.log(JSON.stringify([d.deriveToken(process.argv[2], process.argv[3], 'orderMarker'),"
                  "d.deriveToken('storage-sas-leak', 'ZZZZ0000', 'healthToken', 8),"
                  "d.expectedToken(process.argv[2], process.argv[3], 'found-leak')]))")
        out = subprocess.run([NODE, "-e", script, str(APP / "derive.js"), LAB, SEED], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), [derive_token(LAB, SEED, "orderMarker"),
                                                  derive_token("storage-sas-leak", "ZZZZ0000", "healthToken", 8),
                                                  expected_token(LAB, SEED, "found-leak")])

    def _start(self, role, **env):
        port = _free_port()
        process = subprocess.Popen([NODE, "server.js"], cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env={**os.environ, "PORT": str(port), "BW_ROLE": role, "BW_LAB": LAB, "BW_SEED": SEED, **env})
        self.addCleanup(process.wait, 5)
        self.addCleanup(process.terminate)
        for _ in range(50):
            try:
                _get(port, "/")
                return port
            except OSError:
                time.sleep(0.1)
        self.fail(f"{role} app didn't start")

    def test_portal_ships_with_the_debug_page_and_no_security_headers(self):
        port = self._start("portal", BW_DEBUG="on")
        status, headers, body = _get(port, "/")
        self.assertEqual(status, 200)
        self.assertIn("Contoso Fintech customer portal", body)
        for name in ("Strict-Transport-Security", "X-Content-Type-Options", "Content-Security-Policy"):
            self.assertNotIn(name, headers)
        status, _, body = _get(port, "/debug/config")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["deploymentToken"], expected_token(LAB, SEED, "found-leak"))

    def test_debug_page_is_gone_when_switched_off(self):
        port = self._start("portal")  # BW_DEBUG unset
        self.assertEqual(_get(port, "/debug/config")[0], 404)

    def test_api_ships_with_broken_object_level_authorisation(self):
        port = self._start("api")
        status, _, body = _get(port, "/api/orders/3")  # anonymous, and not the caller's order
        order = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(order["exportMarker"], derive_token(LAB, SEED, "orderMarker"))
        self.assertTrue(order["customerEmail"].endswith("@example.invalid"))
        self.assertEqual(_get(port, "/api/orders/99")[0], 404)
        self.assertEqual(_get(port, "/nope")[0], 404)

    def test_api_lists_only_the_callers_own_orders(self):
        me = "11111111-2222-4333-8444-555555555555"
        port = self._start("api", BW_DEMO_OWNER_OID=me)
        self.assertEqual(json.loads(_get(port, "/api/orders")[2]), [])  # anonymous: none
        mine = json.loads(_get(port, "/api/orders", {"X-MS-CLIENT-PRINCIPAL-ID": me})[2])
        self.assertEqual([o["id"] for o in mine], [1, 2])


class Lab2PlantTest(unittest.TestCase):
    def test_package_holds_just_the_app(self):
        import importlib.util
        import tempfile
        import zipfile
        spec = importlib.util.spec_from_file_location("plant", APP.parent / "seed" / "plant.py")
        plant = importlib.util.module_from_spec(spec)
        env = {"BW_RESOURCE_GROUP": "rg", "BW_NAME_PORTAL": "bw-portal-x", "BW_NAME_API": "bw-api-x"}
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            spec.loader.exec_module(plant)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "app.zip"
            plant.build_zip(target)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(sorted(archive.namelist()), ["derive.js", "package.json", "server.js"])


if __name__ == "__main__":
    unittest.main()
