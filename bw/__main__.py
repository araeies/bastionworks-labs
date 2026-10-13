"""Command-line entry point: `python3 -m bw <command>`."""

import argparse
import sys
from typing import List, Optional

from bw import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bw",
        description="Bastionworks lab kit tool. Every Azure command it runs is printed first.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.add_parser("version", help="print the bw version")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"bw {__version__}")
        return 0
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
