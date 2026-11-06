"""Lab 3's practice self-check (labs/password-spray/checks/local.py): the practice prefix is the published data, and
scoring matches the real check (by account, at most 2 false alarms). No Azure calls."""

import hashlib
import importlib.util
import re
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent / "labs" / "password-spray"
spec = importlib.util.spec_from_file_location("lab3_local", LAB / "checks" / "local.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)

DATA = (LAB / "data" / "practice.kql").read_text(encoding="utf-8")
UPNS = sorted(set(re.findall(r'"([a-z0-9.-]+@contoso-lab\.example)"', DATA)))
# Found by hash at runtime, so the test file never names them.
COMPROMISED = [u for u in UPNS if hashlib.sha256(u.encode()).hexdigest() in local.PRACTICE_COMPROMISED]


class Lab3SelfCheckTest(unittest.TestCase):
    def test_every_hashed_account_is_in_the_published_practice_data(self):
        self.assertEqual(len(COMPROMISED), len(local.PRACTICE_COMPROMISED))

    def test_prefix_is_the_data_without_the_sample_query(self):
        prefix = local.practice_prefix()
        self.assertTrue(prefix.startswith("// Bastionworks lab 3 practice data"))
        self.assertIn("let SigninLogs = datatable(", prefix)
        self.assertTrue(prefix.rstrip().endswith("| project-away Offset;"))
        self.assertNotIn("| take 10", prefix)

    def test_scoring_matches_the_real_check(self):
        others = [u for u in UPNS if u not in COMPROMISED]
        self.assertEqual(local.score(COMPROMISED), (3, 3, 0))
        self.assertEqual(local.score(COMPROMISED + COMPROMISED), (3, 3, 0))  # by account, not by row
        self.assertEqual(local.score(COMPROMISED + others[:2]), (3, 3, 2))
        self.assertEqual(local.score(COMPROMISED[:1] + others), (1, 3, len(others)))
        self.assertEqual(local.score(["", None]), (0, 3, 0))


if __name__ == "__main__":
    unittest.main()
