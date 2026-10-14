import io
import unittest
from datetime import date

from bw.__main__ import main
from bw.az import format_command
from bw.cleanup import run_cleanup
from bw.doctor import run_doctor
from bw.status import run_status
from tests.fake_az import FakeAz, az_error

SUB = {"id": "00000000-0000-0000-0000-000000000001", "name": "bw-playground", "user": {"name": "learner@example.com"}}
PLAYGROUND_TAGS = {"properties": {"tags": {"bastionworks:playground": "true"}}}
ALLOWED = [{"name": "bw-allowed-locations", "parameters": {"listOfAllowedLocations": {"value": ["uksouth", "westeurope"]}}}]


def healthy(**overrides):
    responses = {
        ("version",): {"azure-cli": "2.80.0"},
        ("account", "show"): SUB,
        ("tag", "list"): PLAYGROUND_TAGS,
        ("consumption", "budget", "list"): [{"name": "bw-budget"}],
        ("policy", "assignment", "list"): ALLOWED,
    }
    responses.update(overrides)
    return FakeAz(responses)


class FormatCommandTest(unittest.TestCase):
    def test_quotes_arguments_safely(self):
        self.assertEqual(format_command(["group", "list", "--tag", "a b"]), "$ az group list --tag 'a b'")


class DoctorTest(unittest.TestCase):
    def test_all_checks_pass_on_a_prepared_playground(self):
        report = run_doctor(healthy(), "uksouth")
        self.assertTrue(report.ok, report.checks)

    def test_untagged_subscription_is_refused(self):
        report = run_doctor(healthy(**{("tag", "list"): {"properties": {"tags": {}}}}), "uksouth")
        self.assertFalse(report.ok)
        failed = [c for c in report.checks if not c.ok]
        self.assertEqual([c.name for c in failed], ["Playground tag"])
        self.assertIn("never use a work subscription", failed[0].detail)

    def test_tag_must_be_exactly_true(self):
        report = run_doctor(healthy(**{("tag", "list"): {"properties": {"tags": {"bastionworks:playground": "yes"}}}}), "uksouth")
        self.assertFalse(report.ok)

    def test_missing_budget_fails(self):
        self.assertFalse(run_doctor(healthy(**{("consumption", "budget", "list"): []}), "uksouth").ok)

    def test_disallowed_region_fails(self):
        report = run_doctor(healthy(), "eastus")
        self.assertFalse(report.ok)
        self.assertIn("eastus is not in the allowed regions", [c for c in report.checks if not c.ok][0].detail)

    def test_missing_guardrail_policy_fails(self):
        self.assertFalse(run_doctor(healthy(**{("policy", "assignment", "list"): []}), "uksouth").ok)

    def test_not_signed_in_stops_early(self):
        report = run_doctor(healthy(**{("account", "show"): az_error("Please run 'az login'")}), "uksouth")
        self.assertFalse(report.ok)
        self.assertEqual(report.checks[-1].name, "Signed in")

    def test_cli_exit_code_reflects_result(self):
        out = io.StringIO()
        self.assertEqual(main(["doctor"], az=healthy(), out=out), 0)
        self.assertEqual(main(["doctor"], az=healthy(**{("tag", "list"): {}}), out=io.StringIO()), 1)
        self.assertIn("All checks passed", out.getvalue())


def lab_world(**overrides):
    responses = {
        ("account", "show"): SUB,
        ("group", "list", "--tag"): [{"name": "rg-bw-storage-sas-leak-k7q2mx4p"}],
        ("role", "assignment", "list"): [
            {"id": "/subscriptions/x/providers/Microsoft.Authorization/roleAssignments/1",
             "description": "bastionworks:storage-sas-leak:K7Q2MX4P", "roleDefinitionName": "Reader", "scope": "/subscriptions/x"},
            {"id": "/subscriptions/x/providers/Microsoft.Authorization/roleAssignments/2",
             "description": "something the learner made", "roleDefinitionName": "Owner", "scope": "/subscriptions/x"},
            {"id": "/subscriptions/x/providers/Microsoft.Authorization/roleAssignments/3",
             "description": "bastionworks:storage-sas-leak-2:K7Q2MX4P", "roleDefinitionName": "Reader", "scope": "/subscriptions/x"},
        ],
        ("policy", "assignment", "list"): [
            {"id": "p1", "name": "bw-lab-policy", "scope": "/subscriptions/x", "metadata": {"bastionworksLab": "storage-sas-leak"}},
            {"id": "p2", "name": "bw-allowed-locations", "scope": "/subscriptions/x", "metadata": {"bastionworksLab": "lab-0"}},
        ],
        ("ad", "app", "list"): [],
        ("keyvault", "list-deleted"): [
            {"name": "kv-old", "properties": {"location": "uksouth", "tags": {"bastionworks:lab": "storage-sas-leak"}}},
            {"name": "kv-mine", "properties": {"location": "uksouth", "tags": {}}},
        ],
        ("resource", "list"): [],
    }
    responses.update(overrides)
    return FakeAz(responses)


class CleanupTest(unittest.TestCase):
    def test_deletes_only_what_the_lab_owns_after_confirmation(self):
        az = lab_world()
        # After deletion the fake still returns the original lists, so assert on mutations, not the leftover check.
        out = io.StringIO()
        run_cleanup(az, "storage-sas-leak", out, confirm=lambda _: "storage-sas-leak")
        flat = [" ".join(m) for m in az.mutations]
        self.assertIn("role assignment delete --ids /subscriptions/x/providers/Microsoft.Authorization/roleAssignments/1", flat)
        self.assertFalse(any("roleAssignments/2" in m or "roleAssignments/3" in m for m in flat), flat)
        self.assertIn("policy assignment delete --name bw-lab-policy --scope /subscriptions/x", flat)
        self.assertFalse(any("bw-allowed-locations" in m for m in flat))
        self.assertIn("group delete --name rg-bw-storage-sas-leak-k7q2mx4p --yes", flat)
        self.assertIn("keyvault purge --name kv-old --location uksouth", flat)
        self.assertFalse(any("kv-mine" in m for m in flat))
        # Subscription-scoped role assignments go before the resource group.
        self.assertLess(flat.index(next(m for m in flat if m.startswith("role assignment delete"))),
                        flat.index(next(m for m in flat if m.startswith("group delete"))))

    def test_wrong_confirmation_deletes_nothing(self):
        az = lab_world()
        code = run_cleanup(az, "storage-sas-leak", io.StringIO(), confirm=lambda _: "yes")
        self.assertEqual(code, 1)
        self.assertEqual(az.mutations, [])

    def test_reports_leftovers_and_fails(self):
        az = lab_world()  # the fake keeps returning the same objects, so they look like leftovers
        out = io.StringIO()
        code = run_cleanup(az, "storage-sas-leak", out, confirm=lambda _: "storage-sas-leak")
        self.assertEqual(code, 1)
        self.assertIn("LEFTOVERS", out.getvalue())

    def test_clean_subscription_reports_clean(self):
        az = lab_world(**{("group", "list", "--tag"): [], ("role", "assignment", "list"): [],
                          ("policy", "assignment", "list"): [], ("keyvault", "list-deleted"): []})
        out = io.StringIO()
        self.assertEqual(run_cleanup(az, "storage-sas-leak", out, confirm=lambda _: "x"), 0)
        self.assertIn("Clean: nothing tagged", out.getvalue())
        self.assertEqual(az.mutations, [])

    def test_dry_run_executes_no_mutations(self):
        az = lab_world()
        az.dry_run = True
        out = io.StringIO()
        self.assertEqual(run_cleanup(az, "storage-sas-leak", out, confirm=lambda _: ""), 0)
        self.assertIn("Dry run complete", out.getvalue())


class StatusTest(unittest.TestCase):
    def test_lists_lab_groups_with_cost_and_expiry(self):
        az = FakeAz({
            ("account", "show"): SUB,
            ("group", "list"): [
                {"name": "rg-bw-storage-sas-leak-k7q2mx4p",
                 "tags": {"bastionworks:lab": "storage-sas-leak", "bastionworks:expires": "2026-10-01"}},
                {"name": "my-own-rg", "tags": {}},
            ],
            ("resource", "list"): [
                {"type": "Microsoft.Storage/storageAccounts", "name": "bwsasabc", "resourceGroup": "rg-bw-storage-sas-leak-k7q2mx4p",
                 "tags": {"bastionworks:lab": "storage-sas-leak"}},
            ],
            ("rest",): {"properties": {"columns": [{"name": "Cost"}, {"name": "ResourceGroupName"}, {"name": "Currency"}],
                                       "rows": [[0.0123, "rg-bw-storage-sas-leak-k7q2mx4p", "USD"]]}},
        })
        out = io.StringIO()
        run_status(az, out, today=date(2026, 10, 14))
        text = out.getvalue()
        self.assertIn("rg-bw-storage-sas-leak-k7q2mx4p", text)
        self.assertNotIn("my-own-rg", text)
        self.assertIn("$0.01 yesterday", text)
        self.assertIn("EXPIRED", text)

    def test_cost_unavailable_is_reported_honestly(self):
        az = FakeAz({
            ("account", "show"): SUB,
            ("group", "list"): [{"name": "rg-bw-x-k7q2mx4p", "tags": {"bastionworks:lab": "x"}}],
            ("resource", "list"): [],
            ("rest",): az_error("Cost Management not available"),
        })
        out = io.StringIO()
        run_status(az, out, today=date(2026, 10, 14))
        self.assertIn("cost n/a", out.getvalue())


if __name__ == "__main__":
    unittest.main()
