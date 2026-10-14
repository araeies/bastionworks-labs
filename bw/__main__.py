"""Command-line entry point: `python3 -m bw <command>`."""

import argparse
import sys
from typing import Callable, List, Optional, TextIO

from bw import __version__
from bw.az import Az, AzError, AzNotFound
from bw.cleanup import run_cleanup
from bw.doctor import print_report, run_doctor
from bw.status import run_status

DEFAULT_REGION = "uksouth"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bw",
        description="Bastionworks lab kit tool. Every Azure command it runs is printed first.",
    )
    parser.add_argument("--dry-run", action="store_true", help="print changing commands without running them")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.add_parser("version", help="print the bw version")
    doctor = sub.add_parser("doctor", help="pre-flight checks: sign-in, playground tag, budget, region")
    doctor.add_argument("--region", default=DEFAULT_REGION)
    sub.add_parser("status", help="list Bastionworks resources still running and their recent cost")
    cleanup = sub.add_parser("cleanup", help="remove everything a lab created and confirm nothing remains")
    cleanup.add_argument("lab", help="lab id, e.g. storage-sas-leak")
    cleanup.add_argument("--yes", action="store_true", help="skip the confirmation prompt (for automation)")
    return parser


def main(argv: Optional[List[str]] = None, *, az: Optional[Az] = None, out: Optional[TextIO] = None,
         confirm: Callable[[str], str] = input) -> int:
    out = out if out is not None else sys.stdout  # resolved at call time so redirection works
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"bw {__version__}", file=out)
        return 0
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2

    az = az or Az(out=out, dry_run=args.dry_run)
    try:
        if args.command == "doctor":
            report = run_doctor(az, args.region)
            print_report(report, out)
            return 0 if report.ok else 1
        if args.command == "status":
            return run_status(az, out)
        if args.command == "cleanup":
            return run_cleanup(az, args.lab, out, confirm, assume_yes=args.yes)
    except AzNotFound as error:
        print(str(error), file=sys.stderr)
        return 127
    except AzError as error:
        print(f"\nAzure CLI error: {error}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
