"""bw hint <n> and bw check: learner help that runs entirely from the local kit copy."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, TextIO

from labspec import load_manifest

PRACTICE_BANNER = "PRACTICE ONLY: this is not a verification. Submit on the lab page to get verified."


def kits_home() -> Path:
    return Path(os.environ.get("BW_HOME", Path.home() / ".bastionworks")) / "kits"


def find_kit(lab_id: str, kit_dir: Optional[Path]) -> Path:
    if kit_dir is not None:
        return kit_dir
    candidates = sorted(kits_home().glob(f"{lab_id}@*/{lab_id}"))
    if not candidates:
        raise FileNotFoundError(f"no local kit for '{lab_id}'. Deploy it first, or pass --kit-dir.")
    return candidates[-1]


def run_hint(lab_id: str, number: int, kit_dir: Optional[Path], out: TextIO) -> int:
    manifest = load_manifest(find_kit(lab_id, kit_dir))
    hints = manifest.data["hints"]
    if not 1 <= number <= len(hints):
        print(f"{lab_id} has {len(hints)} hint(s); choose 1–{len(hints)}.", file=out)
        return 1
    print(f"Hint {number} of {len(hints)}:\n", file=out)
    print(manifest.path(hints[number - 1]).read_text(encoding="utf-8"), file=out)
    if number < len(hints):
        print(f"\nStill stuck? bw hint {lab_id} {number + 1}", file=out)
    return 0


def run_check(lab_id: str, kit_dir: Optional[Path], out: TextIO) -> int:
    manifest = load_manifest(find_kit(lab_id, kit_dir))
    script = manifest.kit.get("selfChecks")
    print(PRACTICE_BANNER, file=out)
    if not script:
        print(f"{lab_id} has no local self-checks.", file=out)
        return 0
    path = manifest.path(script)
    print(f"$ {sys.executable} {path}", file=out, flush=True)
    completed = subprocess.run([sys.executable, str(path)], cwd=str(manifest.lab_dir), check=False)
    print(PRACTICE_BANNER, file=out)
    return completed.returncode
