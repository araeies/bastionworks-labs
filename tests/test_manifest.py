import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from labspec.manifest import LintError, load_manifest, trust_level

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "labs" / "sample-lab"


class ManifestLintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name) / "sample-lab"
        shutil.copytree(FIXTURE, self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, change):
        path = self.lab / "lab.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def assert_lint_error(self, fragment):
        with self.assertRaises(LintError) as caught:
            load_manifest(self.lab)
        self.assertTrue(any(fragment in e for e in caught.exception.errors), caught.exception.errors)

    def test_valid_fixture_loads(self):
        manifest = load_manifest(self.lab)
        self.assertEqual(manifest.id, "sample-lab")
        self.assertEqual([trust_level(cp["method"]) for cp in manifest.checkpoints], ["Verified", "Reviewed"])

    def test_trust_cannot_be_declared(self):
        self.edit(lambda d: d["checkpoints"][0].update(trust="Verified"))
        self.assert_lint_error("unexpected property 'trust'")

    def test_needs_a_verified_checkpoint(self):
        self.edit(lambda d: d.update(checkpoints=[d["checkpoints"][1]]))
        self.assert_lint_error("at least one checkpoint must use a Verified method")

    def test_verified_checkpoint_needs_positive_control(self):
        self.edit(lambda d: d["checkpoints"][0].pop("positiveControl"))
        self.assert_lint_error("requires 'positiveControl'")

    def test_sas_submission_must_be_redacted(self):
        self.edit(lambda d: d["checkpoints"][0].update(redactAfterUse=False))
        self.assert_lint_error("redactAfterUse: true")

    def test_issued_sas_validity_is_capped(self):
        def change(d):
            d["checkpoints"][0].update(submit="issuedSasUrl", maxValidityMinutes=60)
        self.edit(change)
        load_manifest(self.lab)
        self.edit(lambda d: d["checkpoints"][0].pop("maxValidityMinutes"))
        self.assert_lint_error("maxValidityMinutes <= 60")

    def test_probe_host_must_be_an_azure_suffix(self):
        self.edit(lambda d: d["checkpoints"][0].update(hostSuffixes=[".evil.example.com"]))
        self.assert_lint_error("hostSuffixes[0]: does not match pattern")

    def test_probe_host_name_must_be_derived(self):
        self.edit(lambda d: d["checkpoints"][0].update(hostName="keyVault"))
        self.assert_lint_error("not defined in kit.names")

    def test_method_submit_mismatch(self):
        self.edit(lambda d: d["checkpoints"][1].update(submit="leakedSasUrl", redactAfterUse=True))
        self.assert_lint_error("cannot accept submit 'leakedSasUrl'")

    def test_missing_referenced_file(self):
        (self.lab / "hints" / "2.md").unlink()
        self.assert_lint_error("'hints/2.md' does not exist")

    def test_path_traversal_rejected(self):
        self.edit(lambda d: d.update(scenario="../outside.md"))
        self.assert_lint_error("does not match pattern")

    def test_private_material_in_public_dir_rejected(self):
        (self.lab / "reference-solution.md").write_text("x", encoding="utf-8")
        self.assert_lint_error("looks like private material")

    def test_debrief_present_publicly_rejected(self):
        (self.lab / "debriefs").mkdir()
        (self.lab / "debriefs" / "sample-lab.md").write_text("x", encoding="utf-8")
        self.assert_lint_error("private debrief")

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlink_rejected(self):
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("x", encoding="utf-8")
        (self.lab / "hints" / "2.md").unlink()
        os.symlink(outside, self.lab / "hints" / "2.md")
        self.assert_lint_error("symlink")

    def test_id_must_match_directory(self):
        self.edit(lambda d: d.update(id="other-lab"))
        self.assert_lint_error("must equal the directory name")

    def test_duplicate_checkpoint_ids(self):
        self.edit(lambda d: d["checkpoints"][1].update(id="leak-dead"))
        self.assert_lint_error("duplicate checkpoint ids")

    def test_invalid_json_reported(self):
        (self.lab / "lab.json").write_text("{not json", encoding="utf-8")
        self.assert_lint_error("not valid JSON")


if __name__ == "__main__":
    unittest.main()
