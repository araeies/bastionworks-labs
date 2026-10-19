"""Every command through bw's real entry point (main), as a learner runs it. The command modules have their own
unit tests; these catch wiring mistakes in main() itself (a duplicated dispatch block once made deploy, hint and
check unreachable, and an undefined name broke deploy --kit-dir)."""

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bw.__main__ import main
from tests.fake_az import FakeAz
from tests.test_manifest import _kitless

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "labs" / "sample-lab"


class MainEntryPointTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name) / "sample-lab"
        shutil.copytree(FIXTURE, self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def run_bw(self, *argv, az=None):
        out = io.StringIO()
        code = main(list(argv), az=az or FakeAz({}), out=out, confirm=lambda _: "no")
        return code, out.getvalue()

    def test_hint_reaches_its_command(self):
        code, text = self.run_bw("hint", "sample-lab", "1", "--kit-dir", str(self.lab))
        self.assertEqual(code, 0)
        self.assertIn("Hint 1 of", text)

    def test_check_reaches_its_command(self):
        with mock.patch("bw.practice.subprocess.run") as run:
            run.return_value.returncode = 0
            code, text = self.run_bw("check", "sample-lab", "--kit-dir", str(self.lab))
        self.assertEqual(code, 0)
        self.assertTrue(run.called)

    def test_deploy_with_a_local_kit_and_no_version(self):
        path = self.lab / "lab.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _kitless(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch("bw.__main__.kits_home", return_value=Path(self.tmp.name) / "kits"):
            code, text = self.run_bw("deploy", "sample-lab", "--seed", "K7Q2-MX4P", "--kit-dir", str(self.lab))
        self.assertEqual(code, 0, text)
        self.assertIn("nothing to deploy", text)

    def test_token_explains_the_format_and_prints_no_token(self):
        code, text = self.run_bw("token", "password-spray")
        self.assertEqual(code, 0)
        self.assertIn("bwt-", text)
        self.assertIn("on your word", text)
        self.assertNotRegex(text, r"bwt-[0-9a-z]{24}")

    def test_unknown_labs_and_bad_seeds_fail_cleanly(self):
        code, _ = self.run_bw("hint", "sample-lab", "99", "--kit-dir", str(self.lab))
        self.assertEqual(code, 1)
        with mock.patch("bw.__main__.kits_home", return_value=Path(self.tmp.name) / "kits"):
            code, _ = self.run_bw("deploy", "sample-lab", "--seed", "!!", "--kit-dir", str(self.lab))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
