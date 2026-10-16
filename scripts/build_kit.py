"""Build a reproducible kit release: kit-<lab>-<version>.tar.gz + SHA256SUMS (ADR-0016).

The archive holds exactly one top-level folder, the lab id, which is what bw's safe_extract expects. The lab
must lint clean, its lab.json version must equal the tag version, and no private material may be inside
(the lint already refuses it). Standard library only.

Usage: python3 scripts/build_kit.py --tag kit-storage-sas-leak-v0.1.0 --out dist
"""

import argparse
import gzip
import hashlib
import io
import re
import sys
import tarfile
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labspec import LintError, load_manifest  # noqa: E402

TAG_PATTERN = re.compile(r"^kit-(?P<lab>[a-z0-9]+(?:-[a-z0-9]+)*)-v(?P<version>\d+\.\d+\.\d+)$")
FIXED_MTIME = 0


def parse_tag(tag: str) -> Tuple[str, str]:
    match = TAG_PATTERN.match(tag)
    if not match:
        raise SystemExit(f"tag must look like kit-<lab-id>-v<major.minor.patch>; got {tag!r}")
    return match.group("lab"), match.group("version")


def kit_files(lab_dir: Path) -> List[Path]:
    files = [p for p in lab_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return sorted(files, key=lambda p: p.relative_to(lab_dir).as_posix())


def build_kit_tarball(lab_dir: Path) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in kit_files(lab_dir):
            data = path.read_bytes()
            info = tarfile.TarInfo(name=f"{lab_dir.name}/{path.relative_to(lab_dir).as_posix()}")
            info.size = len(data)
            info.mtime = FIXED_MTIME
            info.mode = 0o755 if path.suffix in (".sh", ".py") else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=FIXED_MTIME) as gz:
        gz.write(raw.getvalue())
    return compressed.getvalue()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    lab_id, version = parse_tag(args.tag)
    lab_dir = ROOT / "labs" / lab_id
    try:
        manifest = load_manifest(lab_dir)
    except LintError as error:
        raise SystemExit(str(error)) from None
    if manifest.version != version:
        raise SystemExit(f"tag version {version} does not match {lab_id}/lab.json version {manifest.version}")

    args.out.mkdir(parents=True, exist_ok=True)
    name = f"kit-{lab_id}-{version}.tar.gz"
    data = build_kit_tarball(lab_dir)
    (args.out / name).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (args.out / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
    print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
