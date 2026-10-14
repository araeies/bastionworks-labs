import io
import json
import shutil
import tarfile
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bw.deploy import DeployError, derived_names, run_deploy
from bw.kit import KitError, kit_asset_url, safe_extract
from bw.practice import PRACTICE_BANNER, run_hint
from labspec import load_manifest
from tests.fake_az import FakeAz
from tests.test_bw_commands import healthy

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "labs" / "sample-lab"
SEED = "K7Q2-MX4P"


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name) / "sample-lab"
        shutil.copytree(FIXTURE, self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deploys_into_tagged_group_with_derived_names(self):
        az = healthy()
        out = io.StringIO()
        code = run_deploy(az, "sample-lab", SEED, self.lab, "uksouth", out, confirm=lambda _: "deploy",
                          today=date(2026, 10, 14))
        self.assertEqual(code, 0)
        group_create, deployment = az.mutations
        self.assertEqual(group_create[:4], ["group", "create", "--name", "rg-bw-sample-lab-k7q2mx4p"])
        self.assertIn("bastionworks:lab=sample-lab", group_create)
        self.assertIn("bastionworks:seed=K7Q2MX4P", group_create)
        self.assertIn("bastionworks:expires=2026-10-16", group_create)
        self.assertIn("bastionworks:kit=sample-lab@1.0.0", group_create)
        names = json.loads(next(p for p in deployment if p.startswith("names="))[len("names="):])
        self.assertEqual(names, derived_names(load_manifest(self.lab), "K7Q2MX4P"))
        self.assertIn("bw cleanup sample-lab", out.getvalue())

    def test_refuses_when_doctor_fails(self):
        az = healthy({("tag", "list"): {"properties": {"tags": {}}}})
        out = io.StringIO()
        code = run_deploy(az, "sample-lab", SEED, self.lab, "uksouth", out, confirm=lambda _: "deploy")
        self.assertEqual(code, 1)
        self.assertEqual(az.mutations, [])
        self.assertIn("Playground tag", out.getvalue())

    def test_unconfirmed_deploy_changes_nothing(self):
        az = healthy()
        self.assertEqual(run_deploy(az, "sample-lab", SEED, self.lab, "uksouth", io.StringIO(), confirm=lambda _: "y"), 1)
        self.assertEqual(az.mutations, [])

    def test_kit_for_another_lab_is_refused(self):
        with self.assertRaises(DeployError):
            run_deploy(healthy(), "other-lab", SEED, self.lab, "uksouth", io.StringIO(), confirm=lambda _: "deploy")

    def test_subscription_scope_requires_exact_subscription_name(self):
        data = json.loads((self.lab / "lab.json").read_text())
        data["kit"]["scope"] = "subscription"
        (self.lab / "lab.json").write_text(json.dumps(data))
        az = FakeAz({("account", "show"): {"id": "sub-1", "name": "bw-playground"}})
        self.assertEqual(run_deploy(az, "sample-lab", SEED, self.lab, "uksouth", io.StringIO(), confirm=lambda _: "yes"), 1)
        self.assertEqual(az.mutations, [])
        out = io.StringIO()
        self.assertEqual(run_deploy(az, "sample-lab", SEED, self.lab, "uksouth", out, confirm=lambda _: "bw-playground"), 0)
        self.assertEqual(az.mutations[0][:3], ["deployment", "sub", "create"])
        self.assertIn("DEDICATED subscription", out.getvalue())


def _archive(entries):
    """Build a tar.gz from (name, kind, data) tuples; kind is 'file', 'dir', 'symlink'."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, kind, data in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = data
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class SafeExtractTest(unittest.TestCase):
    def extract(self, entries):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "kit.tar.gz"
            archive.write_bytes(_archive(entries))
            dest = Path(tmp) / "out"
            dest.mkdir()
            return safe_extract(archive, dest).name

    def test_extracts_a_normal_kit(self):
        self.assertEqual(self.extract([("sample-lab/lab.json", "file", b"{}")]), "sample-lab")

    def test_rejects_traversal(self):
        with self.assertRaises(KitError):
            self.extract([("sample-lab/../../etc/x", "file", b"x")])

    def test_rejects_absolute_paths(self):
        with self.assertRaises(KitError):
            self.extract([("/tmp/x", "file", b"x")])

    def test_rejects_symlinks(self):
        with self.assertRaises(KitError):
            self.extract([("sample-lab/link", "symlink", "/etc/passwd")])

    def test_rejects_multiple_roots(self):
        with self.assertRaises(KitError):
            self.extract([("a/x", "file", b"x"), ("b/y", "file", b"y")])

    def test_asset_url_is_versioned_and_validated(self):
        self.assertEqual(
            kit_asset_url("storage-sas-leak", "1.2.0"),
            "https://github.com/araeies/bastionworks-labs/releases/download/kit-storage-sas-leak-v1.2.0/kit-storage-sas-leak-1.2.0.tar.gz",
        )
        with self.assertRaises(KitError):
            kit_asset_url("x;rm", "1.0.0")


class HintTest(unittest.TestCase):
    def test_shows_hint_and_bounds(self):
        out = io.StringIO()
        self.assertEqual(run_hint("sample-lab", 1, FIXTURE, out), 0)
        self.assertIn("Hint 1 of 2", out.getvalue())
        self.assertEqual(run_hint("sample-lab", 3, FIXTURE, io.StringIO()), 1)

    def test_practice_banner_is_explicit(self):
        self.assertIn("not a verification", PRACTICE_BANNER)


if __name__ == "__main__":
    unittest.main()
