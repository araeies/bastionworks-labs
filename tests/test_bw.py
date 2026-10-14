import io
import json
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from bw import __version__
from bw.__main__ import main
from scripts import build_release


class VersionCommandTest(unittest.TestCase):
    def test_prints_version(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), f"bw {__version__}")

    def test_no_command_prints_help_and_fails(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main([])
        self.assertEqual(code, 2)
        self.assertIn("usage: bw", err.getvalue())


class BuildReleaseTest(unittest.TestCase):
    def test_tarball_is_reproducible(self):
        self.assertEqual(build_release.build_tarball(__version__), build_release.build_tarball(__version__))

    def test_tarball_contains_only_package_files_with_fixed_metadata(self):
        data = build_release.build_tarball(__version__)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            members = tar.getmembers()
        self.assertTrue(members)
        names = {m.name for m in members}
        self.assertIn(f"bw-{__version__}/labspec/schema/manifest.schema.json", names)
        for member in members:
            self.assertTrue(member.name.startswith((f"bw-{__version__}/bw/", f"bw-{__version__}/labspec/")), member.name)
            self.assertNotIn("__pycache__", member.name)
            self.assertNotIn("..", member.name)
            self.assertEqual(member.mtime, 0)
            self.assertEqual((member.uid, member.gid), (0, 0))
            self.assertTrue(member.isfile())

    def test_rejects_tag_that_does_not_match_package_version(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            build_release.main(["--version", "9.9.9", "--out", tmp])

    def test_rejects_malformed_version(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            build_release.main(["--version", "1.0; rm -rf /", "--out", tmp])

    def test_sbom_is_cyclonedx_accepted_by_actions_attest(self):
        sbom = build_release.build_sbom("0.0.1-test.2")
        # actions/attest requires bomFormat, serialNumber and specVersion (src/sbom.ts).
        self.assertEqual(sbom["bomFormat"], "CycloneDX")
        self.assertEqual(sbom["specVersion"], "1.5")
        self.assertRegex(sbom["serialNumber"], r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        self.assertEqual(sbom, build_release.build_sbom("0.0.1-test.2"))  # reproducible

    def test_writes_tarball_and_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(build_release.main(["--version", __version__, "--out", tmp]), 0)
            sums = (Path(tmp) / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertRegex(sums, rf"^[0-9a-f]{{64}}  bw-{__version__}\.tar\.gz\n$")
            # The release workflow attests dist/bw.cdx.json; it must be written and parse as the CycloneDX
            # document actions/attest accepts (bomFormat + serialNumber + specVersion).
            sbom = json.loads((Path(tmp) / "bw.cdx.json").read_text(encoding="utf-8"))
            for field in ("bomFormat", "serialNumber", "specVersion"):
                self.assertIn(field, sbom)


if __name__ == "__main__":
    unittest.main()
