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


def _kitless(d):
    """Turn the sample into a lab-3-style lab: nothing to deploy, a hidden-dataset rule plus a reviewed write-up."""
    d["kit"] = {"scope": "none", "selfChecks": "checks/local.py"}
    d["learnerCostEstimateUsd"] = 0
    d["checkpoints"] = [
        {"id": "detect", "title": "Your rule catches the attack", "method": "hiddenDataset", "submit": "repoAtCommit",
         "repoFile": "detections/password-spray.kql", "dataset": "private:password-spray/v1",
         "positiveControl": "Benign lookalikes must not be flagged, so a rule that returns everything fails."},
        {"id": "runbook", "title": "Write the rule's runbook entry", "method": "rubricReview", "submit": "repoAtCommit",
         "repoFile": "detections/password-spray.md", "rubric": "rubrics/incident-note.md"},
    ]


class KitlessAndRepoFileTest(ManifestLintTest):
    def test_kitless_lab_loads(self):
        self.edit(_kitless)
        manifest = load_manifest(self.lab)
        self.assertEqual(manifest.kit["scope"], "none")
        self.assertEqual(manifest.checkpoints[0]["repoFile"], "detections/password-spray.kql")

    def test_kitless_lab_cannot_set_deployment_fields(self):
        self.edit(lambda d: (_kitless(d), d["kit"].update({"template": "infra/main.bicep", "names": {}})))
        self.assert_lint_error("can't set template, names")

    def test_kitless_lab_must_cost_nothing(self):
        self.edit(lambda d: (_kitless(d), d.update({"learnerCostEstimateUsd": 0.5})))
        self.assert_lint_error("learnerCostEstimateUsd must be 0")

    def test_kitless_lab_cannot_probe_or_scan(self):
        def change(d):
            _kitless(d)
            d["checkpoints"].append({"id": "probe", "title": "Something answers", "method": "externalProbe", "submit": "url",
                                     "hostSuffixes": [".blob.core.windows.net"], "hostName": "x", "expect": {"status": [200]},
                                     "positiveControl": "A deployed resource would have to answer, but there are none."})
        self.edit(change)
        self.assert_lint_error("externalProbe needs deployed resources")

    def test_deploying_kit_still_needs_its_fields(self):
        self.edit(lambda d: d["kit"].pop("cleanup"))
        self.assert_lint_error("requires 'cleanup'")

    def test_hidden_dataset_repo_submission_needs_a_kql_file(self):
        self.edit(lambda d: (_kitless(d), d["checkpoints"][0].update({"repoFile": "detections/rule.txt"})))
        self.assert_lint_error("repoFile ending in .kql")

    def test_repo_file_only_for_repo_submissions_and_reading_methods(self):
        self.edit(lambda d: d["checkpoints"][0].update({"repoFile": "x.md"}))  # leak-dead: externalProbe + leakedSasUrl
        self.assert_lint_error("repoFile only applies to repoAtCommit submissions")
        with self.assertRaises(LintError) as caught:
            load_manifest(self.lab)
        self.assertTrue(any("only applies to hiddenDataset and rubricReview" in e for e in caught.exception.errors))

    def test_repo_file_must_stay_inside_the_repo(self):
        self.edit(lambda d: (_kitless(d), d["checkpoints"][1].update({"repoFile": "../outside.md"})))
        self.assert_lint_error("repoFile")

    def test_repo_file_rejects_dot_segments_anywhere(self):
        for bad in ("detections/../../etc/x.kql", "detections/./x.kql", "detections//x.kql"):
            self.edit(lambda d, bad=bad: (_kitless(d), d["checkpoints"][0].update({"repoFile": bad})))
            self.assert_lint_error("plain path inside the repo")


def _url_probe(d, **expect):
    """Turn the fixture's first checkpoint into a plain-URL probe with the given expectations."""
    cp = d["checkpoints"][0]
    cp.pop("redactAfterUse", None)
    cp.update(submit="url", expect={"status": [200], **expect})


class ProbeProfileLintTest(unittest.TestCase):
    """The HTTP probe profile (lab 2): headers, CORS, extra requests, probePath."""

    setUp, tearDown = ManifestLintTest.setUp, ManifestLintTest.tearDown
    edit, assert_lint_error = ManifestLintTest.edit, ManifestLintTest.assert_lint_error

    REDIRECT = {"scheme": "http", "path": "/", "status": [301, 308], "locationPrefix": "https://{host}/"}

    def test_full_profile_loads(self):
        self.edit(lambda d: (_url_probe(d, headers={"X-Content-Type-Options": "^nosniff$"}, corsDenies="https://evil.example",
                                        bodyExcludesDerived="orderMarker",
                                        also=[self.REDIRECT, {"scheme": "https", "path": "/debug/config", "status": [404]}]),
                             d["checkpoints"][0].update(probePath="/api/orders/1")))
        load_manifest(self.lab)

    def test_azurewebsites_suffix_without_a_middle_label(self):
        self.edit(lambda d: (_url_probe(d), d["checkpoints"][0].update(hostSuffixes=[".azurewebsites.net"])))
        load_manifest(self.lab)
        for bad in (".azurewebsites.net.evil.example", ".evilazurewebsites.net", "azurewebsites.net"):
            self.edit(lambda d, bad=bad: d["checkpoints"][0].update(hostSuffixes=[bad]))
            self.assert_lint_error("hostSuffixes[0]: does not match pattern")

    def test_plain_http_only_for_the_redirect_check(self):
        for bad in ({**self.REDIRECT, "path": "/debug/config"}, {**self.REDIRECT, "status": [200]},
                    {**self.REDIRECT, "status": [302]}, {**self.REDIRECT, "locationPrefix": "https://evil.example/"},
                    {"scheme": "http", "path": "/", "status": [301]}):
            self.edit(lambda d, bad=bad: _url_probe(d, also=[bad]))
            self.assert_lint_error("plain http is only for the redirect check")

    def test_location_prefix_only_knows_host(self):
        self.edit(lambda d: _url_probe(d, also=[{"scheme": "https", "path": "/", "status": [302],
                                                  "locationPrefix": "https://{tenant}.example/"}]))
        self.assert_lint_error("may only use the {host} placeholder")

    def test_header_names_and_patterns_are_checked(self):
        self.edit(lambda d: _url_probe(d, headers={"Bad Header": "x"}))
        self.assert_lint_error("not a plain HTTP header name")
        self.edit(lambda d: _url_probe(d, headers={"X-Thing": "(unclosed"}))
        self.assert_lint_error("pattern doesn't compile")
        self.edit(lambda d: _url_probe(d, headers={f"X-H{i}": "." for i in range(9)}))
        self.assert_lint_error("at most 8 expected headers")

    def test_profile_fields_only_on_url_probes(self):
        self.edit(lambda d: d["checkpoints"][0]["expect"].update(corsDenies="https://evil.example"))  # leakedSasUrl
        self.assert_lint_error("only apply to submit 'url' probes")

    def test_probe_path_only_on_external_probes(self):
        self.edit(lambda d: d["checkpoints"][1].update(probePath="/"))
        self.assert_lint_error("probePath only applies to externalProbe")
