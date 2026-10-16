import io
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bw.kit import safe_extract
from scripts import build_kit

LAB_DIR = Path(__file__).resolve().parent.parent / "labs" / "storage-sas-leak"


class BuildKitTest(unittest.TestCase):
    def test_tag_parsing(self):
        self.assertEqual(build_kit.parse_tag("kit-storage-sas-leak-v0.1.0"), ("storage-sas-leak", "0.1.0"))
        for bad in ("v0.1.0", "kit-storage-sas-leak-0.1.0", "kit-Storage-v0.1.0", "kit-x-v1.0"):
            with self.assertRaises(SystemExit):
                build_kit.parse_tag(bad)

    def test_kit_is_reproducible(self):
        self.assertEqual(build_kit.build_kit_tarball(LAB_DIR), build_kit.build_kit_tarball(LAB_DIR))

    def test_kit_round_trips_through_bw_safe_extract(self):
        data = build_kit.build_kit_tarball(LAB_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "kit.tar.gz"
            archive.write_bytes(data)
            dest = Path(tmp) / "out"
            dest.mkdir()
            root = safe_extract(archive, dest)
            self.assertEqual(root.name, "storage-sas-leak")
            self.assertTrue((root / "lab.json").is_file())
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                self.assertTrue(member.name.startswith("storage-sas-leak/"), member.name)
                self.assertEqual(member.mtime, 0)

    def test_version_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            build_kit.main(["--tag", "kit-storage-sas-leak-v9.9.9", "--out", tmp])

    def test_builds_asset_with_checksum(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            self.assertEqual(build_kit.main(["--tag", "kit-storage-sas-leak-v0.1.0", "--out", tmp]), 0)
            self.assertTrue((Path(tmp) / "kit-storage-sas-leak-0.1.0.tar.gz").is_file())
            self.assertIn("kit-storage-sas-leak-0.1.0.tar.gz", (Path(tmp) / "SHA256SUMS").read_text())


if __name__ == "__main__":
    unittest.main()
