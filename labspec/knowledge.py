"""Knowledge checks and self-issued tokens (platform ADR-0028).

Knowledge checks: the QUESTIONS are public (a lab's `questionsFile`, never with answers); the answer key is private
(the Verifier). Each learner's seed picks `pick` of the questions and shuffles each question's options, so learners
see different sets. The web app (TypeScript) and the Verifier (Python) must select identically: the ordering is a
plain SHA-256 sort, mirrored in the platform and pinned by the test vectors in tests/test_knowledge.py.

Self-issued tokens: the kit plants `expected_token()` where only the in-VM step reveals it. Anyone with the public
code and their seed could compute it, so a token is honestly SELF-REPORTED: it records that a learner says they
reached the step. It is never presented as verified.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from labspec.seed import _DOMAIN, derive_token, normalise_seed

_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Keys that would put answers in the public repo. Checked at every depth, case-insensitively.
FORBIDDEN_KEYS = {"answer", "answers", "correct", "iscorrect", "correctoption", "solution", "explanation", "key"}
TOKEN_PREFIX = "bwt-"


class QuestionsError(ValueError):
    pass


def _forbidden_keys(value: Any, where: str, found: List[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                found.append(f"{where}.{k}")
            _forbidden_keys(v, f"{where}.{k}", found)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _forbidden_keys(v, f"{where}[{i}]", found)


def validate_questions(doc: Any) -> Dict[str, Any]:
    """The public questions document, checked. Raises QuestionsError listing every problem."""
    errors: List[str] = []
    if not isinstance(doc, dict):
        raise QuestionsError("questions file must be a JSON object")
    leaked: List[str] = []
    _forbidden_keys(doc, "$", leaked)
    if leaked:
        errors.append(f"questions file must not contain answers ({', '.join(leaked)}): the answer key is private")
    pick, questions = doc.get("pick"), doc.get("questions")
    if set(doc) - {"pick", "passPercent", "questions"}:
        errors.append(f"unexpected keys: {sorted(set(doc) - {'pick', 'passPercent', 'questions'})}")
    if not isinstance(questions, list) or not questions:
        errors.append("questions must be a non-empty list")
        questions = []
    if not isinstance(pick, int) or isinstance(pick, bool) or not 3 <= pick <= 10:
        errors.append("pick must be an integer from 3 to 10")
    elif len(questions) < pick:
        errors.append(f"pick is {pick} but there are only {len(questions)} questions")
    pass_percent = doc.get("passPercent", 80)
    if not isinstance(pass_percent, int) or isinstance(pass_percent, bool) or not 50 <= pass_percent <= 100:
        errors.append("passPercent must be an integer from 50 to 100")
    seen = set()
    for i, q in enumerate(questions):
        where = f"questions[{i}]"
        if not isinstance(q, dict) or set(q) != {"id", "stem", "options"}:
            errors.append(f"{where} must have exactly id, stem and options")
            continue
        if not isinstance(q["id"], str) or not _ID.match(q["id"]) or q["id"] in seen:
            errors.append(f"{where}: id must be unique, lower-case words joined by '-'")
        seen.add(q.get("id"))
        if not isinstance(q["stem"], str) or not 10 <= len(q["stem"]) <= 500:
            errors.append(f"{where}: stem must be 10-500 characters")
        options = q["options"]
        if not isinstance(options, list) or not 3 <= len(options) <= 6:
            errors.append(f"{where}: options must be a list of 3-6")
            continue
        option_ids = [o.get("id") if isinstance(o, dict) else None for o in options]
        if any(not isinstance(o, dict) or set(o) != {"id", "text"} for o in options) or len(set(option_ids)) != len(options) \
                or any(not isinstance(x, str) or not re.match(r"^[a-z]$", x) for x in option_ids):
            errors.append(f"{where}: each option needs a unique one-letter id and text, nothing else")
        if any(isinstance(o, dict) and (not isinstance(o.get("text"), str) or not 1 <= len(o["text"]) <= 300) for o in options):
            errors.append(f"{where}: option text must be 1-300 characters")
    if errors:
        raise QuestionsError("; ".join(errors))
    return {"pick": pick, "passPercent": pass_percent, "questions": questions}


def load_questions(path: Path) -> Dict[str, Any]:
    try:
        return validate_questions(json.loads(Path(path).read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise QuestionsError(f"questions file is not valid JSON: {error}") from None


def _order_key(lab_id: str, seed: str, checkpoint_id: str, *parts: str) -> str:
    message = "/".join((_DOMAIN, lab_id, normalise_seed(seed), f"kc-{checkpoint_id}", *parts))
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def select_questions(doc: Dict[str, Any], lab_id: str, seed: str, checkpoint_id: str) -> List[Dict[str, Any]]:
    """This learner's questions: `pick` of them, in seed order, each with its options in seed order. Mirrored exactly
    by the web app (platform apps/web/src/lib/learner/knowledge.ts); keep both in step with the test vectors."""
    ordered = sorted(doc["questions"], key=lambda q: _order_key(lab_id, seed, checkpoint_id, q["id"]))[: doc["pick"]]
    return [{"id": q["id"], "stem": q["stem"],
             "options": sorted(q["options"], key=lambda o: _order_key(lab_id, seed, checkpoint_id, q["id"], o["id"]))}
            for q in ordered]


def expected_token(lab_id: str, seed: str, checkpoint_id: str) -> str:
    """The self-issued token a kit plants for this learner and checkpoint (Self-reported; see the module docstring)."""
    return TOKEN_PREFIX + derive_token(lab_id, seed, f"token-{checkpoint_id}")
