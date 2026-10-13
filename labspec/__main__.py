"""Lint lab packages: `python3 -m labspec lint labs/storage-sas-leak` or `python3 -m labspec lint --all labs`."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from labspec.manifest import MANIFEST_NAME, LintError, load_manifest, trust_level


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="labspec")
    sub = parser.add_subparsers(dest="command", required=True)
    lint = sub.add_parser("lint", help="validate lab packages against the schema and lint rules")
    lint.add_argument("paths", nargs="+", type=Path)
    lint.add_argument("--all", action="store_true", help="treat each path as a directory of labs")
    args = parser.parse_args(argv)

    lab_dirs: List[Path] = []
    for path in args.paths:
        if args.all:
            lab_dirs += sorted(p.parent for p in path.glob(f"*/{MANIFEST_NAME}"))
        else:
            lab_dirs.append(path)
    if not lab_dirs:
        print("no lab packages found", file=sys.stderr)
        return 1

    failed = 0
    for lab_dir in lab_dirs:
        try:
            manifest = load_manifest(lab_dir)
        except LintError as error:
            failed += 1
            print(f"FAIL {lab_dir}")
            for message in error.errors:
                print(f"  - {message}")
            continue
        levels = ", ".join(f"{cp['id']}={trust_level(cp['method'])}" for cp in manifest.checkpoints)
        print(f"ok   {manifest.id}@{manifest.version} ({levels})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
