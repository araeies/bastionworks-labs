"""Load, validate and lint a lab package (lab.json + the files it references)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from labspec.validator import validate

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "manifest.schema.json"
MANIFEST_NAME = "lab.json"

# Trust is derived from the method, never declared, so a lab cannot overstate a checkpoint (brief §11).
_TRUST = {
    "hiddenDataset": "Verified",
    "externalProbe": "Verified",
    "artefactScan": "Verified",
    "rubricReview": "Reviewed",
    "knowledgeCheck": "Reviewed",
    "selfIssuedToken": "Self-reported",
}
VERIFIED_METHODS = {m for m, t in _TRUST.items() if t == "Verified"}
SAS_SUBMISSIONS = {"leakedSasUrl", "issuedSasUrl"}

# Which submission types each method may accept.
_ALLOWED_SUBMIT = {
    "hiddenDataset": {"repoAtCommit", "text"},
    "externalProbe": {"url", "leakedSasUrl", "issuedSasUrl"},
    "artefactScan": {"repoAtCommit"},
    "rubricReview": {"repoAtCommit", "text"},
    "knowledgeCheck": {"answers"},
    "selfIssuedToken": {"token"},
}
# Fields each method must provide.
_REQUIRED_FIELDS = {
    "hiddenDataset": ("dataset", "positiveControl"),
    "externalProbe": ("hostSuffixes", "hostName", "expect", "positiveControl"),
    "artefactScan": ("rules", "positiveControl"),
    "rubricReview": ("rubric",),
    "knowledgeCheck": ("questions",),
    "selfIssuedToken": (),
}
# File names that suggest answers or private material in the public repo.
_FORBIDDEN_NAME_PARTS = ("debrief", "solution", "answer", "answers", "reference-solution", "hidden")


class LintError(Exception):
    def __init__(self, lab_dir: Path, errors: List[str]):
        self.lab_dir = lab_dir
        self.errors = errors
        super().__init__(f"{lab_dir}: {len(errors)} error(s)\n  " + "\n  ".join(errors))


def trust_level(method: str) -> str:
    return _TRUST[method]


class Manifest:
    def __init__(self, lab_dir: Path, data: Dict[str, Any]):
        self.lab_dir = lab_dir
        self.data = data

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def version(self) -> str:
        return self.data["version"]

    @property
    def kit(self) -> Dict[str, Any]:
        return self.data["kit"]

    @property
    def checkpoints(self) -> List[Dict[str, Any]]:
        return self.data["checkpoints"]

    def path(self, relative: str) -> Path:
        return self.lab_dir / relative


def _load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _contained_file(lab_dir: Path, relative: str) -> Optional[str]:
    """Return an error if `relative` is missing, escapes the lab directory, or goes through a symlink."""
    if ".." in Path(relative).parts:
        return f"path '{relative}' must not contain '..'"
    candidate = lab_dir / relative
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        return f"referenced file '{relative}' does not exist"
    try:
        resolved.relative_to(lab_dir.resolve())
    except ValueError:
        return f"path '{relative}' resolves outside the lab directory"
    for part in [candidate] + list(candidate.parents):
        if part == lab_dir:
            break
        if part.is_symlink():
            return f"path '{relative}' goes through a symlink; symlinks are not allowed in kits"
    if not resolved.is_file():
        return f"'{relative}' is not a regular file"
    return None


def _semantic_errors(lab_dir: Path, data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    kit = data["kit"]

    if data["id"] != lab_dir.name:
        errors.append(f"id '{data['id']}' must equal the directory name '{lab_dir.name}'")

    referenced = [data["scenario"], kit["template"], kit["cleanup"]] + list(data["hints"])
    for key in ("seed", "selfChecks"):
        if key in kit:
            referenced.append(kit[key])
    referenced += [cp["rubric"] for cp in data["checkpoints"] if "rubric" in cp]
    for relative in referenced:
        problem = _contained_file(lab_dir, relative)
        if problem:
            errors.append(problem)

    ids = [cp["id"] for cp in data["checkpoints"]]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        errors.append(f"duplicate checkpoint ids: {duplicates}")

    if not any(cp["method"] in VERIFIED_METHODS for cp in data["checkpoints"]):
        errors.append("at least one checkpoint must use a Verified method (hiddenDataset, externalProbe, artefactScan)")

    for cp in data["checkpoints"]:
        where = f"checkpoint '{cp['id']}'"
        method, submit = cp["method"], cp["submit"]
        if submit not in _ALLOWED_SUBMIT[method]:
            errors.append(f"{where}: method {method} cannot accept submit '{submit}'")
        for field in _REQUIRED_FIELDS[method]:
            if field not in cp:
                errors.append(f"{where}: method {method} requires '{field}'")
        if method == "externalProbe":
            if "status" not in cp.get("expect", {}):
                errors.append(f"{where}: externalProbe requires expect.status")
            if cp.get("hostName") and cp["hostName"] not in kit["names"]:
                errors.append(f"{where}: hostName '{cp['hostName']}' is not defined in kit.names")
        if submit in SAS_SUBMISSIONS and cp.get("redactAfterUse") is not True:
            errors.append(f"{where}: SAS submissions must set redactAfterUse: true (exception E6)")
        if submit == "issuedSasUrl" and cp.get("maxValidityMinutes", 61) > 60:
            errors.append(f"{where}: issuedSasUrl requires maxValidityMinutes <= 60 (exception E6)")
        if submit not in SAS_SUBMISSIONS and ("redactAfterUse" in cp or "maxValidityMinutes" in cp):
            errors.append(f"{where}: redactAfterUse/maxValidityMinutes only apply to SAS submissions")

    private_relative = data["debrief"][len("private:"):]
    if (lab_dir / private_relative).exists():
        errors.append(f"private debrief '{private_relative}' exists in the public lab directory")
    for path in lab_dir.rglob("*"):
        lowered = path.name.lower()
        if any(part in lowered for part in _FORBIDDEN_NAME_PARTS):
            errors.append(f"'{path.relative_to(lab_dir)}' looks like private material; it must live in verifier-private")
        if path.is_symlink():
            errors.append(f"'{path.relative_to(lab_dir)}' is a symlink; symlinks are not allowed in kits")
    return errors


def load_manifest(lab_dir: Path) -> Manifest:
    """Parse and fully lint a lab package. Raises LintError listing every problem found."""
    lab_dir = Path(lab_dir)
    manifest_path = lab_dir / MANIFEST_NAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LintError(lab_dir, [f"{MANIFEST_NAME} not found"]) from None
    except json.JSONDecodeError as error:
        raise LintError(lab_dir, [f"{MANIFEST_NAME} is not valid JSON: {error}"]) from None

    errors = validate(data, _load_schema())
    if not errors:
        errors = _semantic_errors(lab_dir, data)
    if errors:
        raise LintError(lab_dir, errors)
    return Manifest(lab_dir, data)
