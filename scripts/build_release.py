"""Build a reproducible bw release tarball and its SHA256SUMS (ADR-0016).

Reproducible: sorted entries, fixed mtime/owner/mode, no compression timestamp, so the same commit always
produces the same bytes and the same hash. Standard library only.

Usage: python3 scripts/build_release.py --version 0.0.1 --out dist
"""

import argparse
import gzip
import json
import hashlib
import io
import re
import sys
import tarfile
import uuid
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "bw"
# bw imports labspec, so both ship in the release (one manifest parser for kit tooling and Verifier).
PACKAGE_DIRS = (ROOT / "bw", ROOT / "labspec")
FIXED_MTIME = 0
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def package_files() -> List[Path]:
    files = [
        p for d in PACKAGE_DIRS for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    ]
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def read_package_version() -> str:
    text = (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE)
    if not match:
        raise SystemExit("cannot find __version__ in bw/__init__.py")
    return match.group(1)


def build_tarball(version: str) -> bytes:
    top = f"bw-{version}"
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in package_files():
            data = path.read_bytes()
            info = tarfile.TarInfo(name=f"{top}/{path.relative_to(ROOT).as_posix()}")
            info.size = len(data)
            info.mtime = FIXED_MTIME
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=FIXED_MTIME) as gz:
        gz.write(raw.getvalue())
    return compressed.getvalue()


def build_sbom(version: str) -> dict:
    """Minimal CycloneDX 1.5 SBOM. bw and labspec use only the Python standard library, so the component
    list is empty. serialNumber is required by actions/attest; it is a UUIDv5 of the version, so the same
    release always gets the same SBOM bytes (reproducible)."""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'https://github.com/araeies/bastionworks-labs/bw/{version}')}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "bw",
                "version": version,
                "licenses": [{"license": {"name": "PolyForm-Shield-1.0.0"}}],
            }
        },
        "components": [],
    }


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not VERSION_PATTERN.match(args.version):
        raise SystemExit(f"invalid version: {args.version!r}")
    package_version = read_package_version()
    if args.version.split("-")[0] != package_version:
        raise SystemExit(f"tag version {args.version} does not match bw/__init__.py version {package_version}")

    args.out.mkdir(parents=True, exist_ok=True)
    name = f"bw-{args.version}.tar.gz"
    data = build_tarball(args.version)
    (args.out / name).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (args.out / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
    print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
