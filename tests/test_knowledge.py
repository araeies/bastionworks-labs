import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from labspec.knowledge import QuestionsError, expected_token, load_questions, select_questions, validate_questions
from labspec.manifest import LintError, load_manifest

ROOT = Path(__file__).resolve().parents[1]
LAB0 = ROOT / "labs" / "lab-0"
QUESTIONS = LAB0 / "questions" / "why-it-matters.json"

# Test vectors: the platform's TypeScript port (apps/web/src/lib/learner/knowledge.ts) must produce exactly these.
VECTOR_SEED = "K7Q2MX4P"
VECTOR_QUESTION_ORDER = ["dedicated-subscription", "owner-and-guardrails", "playground-tag", "budget-at-limit", "policy-vs-identity"]
VECTOR_FIRST_OPTION_ORDER = ["d", "a", "c", "b"]
VECTOR_TOKEN = "bwt-2indp2iya2t2briotpon4uxz"  # expected_token("password-spray", VECTOR_SEED, "in-vm")


class QuestionsFileTest(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))

    def refuse(self, doc, fragment):
        with self.assertRaises(QuestionsError) as caught:
            validate_questions(doc)
        self.assertIn(fragment, str(caught.exception))

    def test_lab0_questions_are_valid_and_contain_no_answers(self):
        loaded = load_questions(QUESTIONS)
        self.assertEqual((loaded["pick"], loaded["passPercent"], len(loaded["questions"])), (5, 80, 8))

    def test_answer_like_keys_are_refused_at_any_depth(self):
        for path in (("questions", 0, "answer"), ("questions", 0, "options", 1, "correct"), ("solution",)):
            doc = copy.deepcopy(self.doc)
            target = doc
            for step in path[:-1]:
                target = target[step]
            target[path[-1]] = "b"
            self.refuse(doc, "must not contain answers")

    def test_shape_rules(self):
        cases = [
            (lambda d: d.update(pick=2), "pick must be an integer from 3 to 10"),
            (lambda d: d.update(pick=9), "only 8 questions"),
            (lambda d: d.update(passPercent=40), "passPercent"),
            (lambda d: d["questions"][1].update(id=d["questions"][0]["id"]), "unique"),
            (lambda d: d["questions"][0].update(stem="short"), "stem must be"),
            (lambda d: d["questions"][0]["options"].pop(), None),  # 3 options is still fine
            (lambda d: d["questions"][0].update(options=d["questions"][0]["options"][:2]), "3-6"),
            (lambda d: d["questions"][0]["options"][0].update(id="aa"), "one-letter id"),
            (lambda d: d["questions"][0]["options"][1].update(id="a"), "one-letter id"),
            (lambda d: d.update(extra=1), "unexpected keys"),
        ]
        for change, fragment in cases:
            doc = copy.deepcopy(self.doc)
            change(doc)
            if fragment is None:
                validate_questions(doc)
            else:
                self.refuse(doc, fragment)
        with self.assertRaises(QuestionsError):
            validate_questions([])

    def test_bad_json_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "q.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(QuestionsError):
                load_questions(bad)


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_questions(QUESTIONS)

    def test_vectors_pin_the_order_for_the_typescript_port(self):
        picked = select_questions(self.doc, "lab-0", VECTOR_SEED, "why-it-matters")
        self.assertEqual([q["id"] for q in picked], VECTOR_QUESTION_ORDER)
        self.assertEqual([o["id"] for o in picked[0]["options"]], VECTOR_FIRST_OPTION_ORDER)
        self.assertEqual(expected_token("password-spray", VECTOR_SEED, "in-vm"), VECTOR_TOKEN)

    def test_sets_differ_between_learners_and_are_stable(self):
        a = select_questions(self.doc, "lab-0", "K7Q2MX4P", "why-it-matters")
        self.assertEqual(a, select_questions(self.doc, "lab-0", "k7q2-mx4p", "why-it-matters"))  # seed normalised
        others = {tuple(q["id"] for q in select_questions(self.doc, "lab-0", s, "why-it-matters"))
                  for s in ("ABCD1234", "ZZZZ0000", "QRST5678", "MNPQ2345")}
        self.assertGreater(len(others), 1)
        for q in a:
            self.assertNotIn("answer", json.dumps(q))

    def test_tokens_are_per_learner_and_per_checkpoint(self):
        self.assertNotEqual(expected_token("password-spray", "K7Q2MX4P", "in-vm"), expected_token("password-spray", "ABCD1234", "in-vm"))
        self.assertNotEqual(expected_token("password-spray", "K7Q2MX4P", "in-vm"), expected_token("password-spray", "K7Q2MX4P", "other"))
        self.assertRegex(expected_token("x", "K7Q2MX4P", "y"), r"^bwt-[0-9a-z]{24}$")


class ManifestKnowledgeLintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name) / "lab-0"
        shutil.copytree(LAB0, self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, change):
        path = self.lab / "lab.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def lint_errors(self):
        try:
            load_manifest(self.lab)
        except LintError as error:
            return error.errors
        return []

    def test_knowledge_check_needs_its_public_questions(self):
        self.edit(lambda d: d["checkpoints"][1].pop("questionsFile"))
        self.assertTrue(any("requires 'questionsFile'" in e for e in self.lint_errors()))

    def test_answers_in_the_public_questions_file_fail_the_lint(self):
        q = self.lab / "questions" / "why-it-matters.json"
        doc = json.loads(q.read_text(encoding="utf-8"))
        doc["questions"][0]["answer"] = "b"
        q.write_text(json.dumps(doc), encoding="utf-8")
        self.assertTrue(any("must not contain answers" in e for e in self.lint_errors()))

    def test_questions_file_only_on_knowledge_checks(self):
        self.edit(lambda d: d["checkpoints"][0].update(questionsFile="questions/why-it-matters.json"))
        self.assertTrue(any("questionsFile only applies to knowledgeCheck" in e for e in self.lint_errors()))


if __name__ == "__main__":
    unittest.main()
