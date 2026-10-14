"""Command-line entry point: `python3 -m bw <command>`."""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, TextIO

from bw import __version__
from bw.az import Az, AzError, AzNotFound
from bw.cleanup import run_cleanup
from bw.deploy import DeployError, run_deploy
from bw.kit import KitError, resolve_kit_dir
from bw.practice import kits_home, run_check, run_hint
from bw.doctor import print_report, run_doctor
from bw.status import run_status
from labspec import InvalidSeed, LintError
from bw.doctor import print_report, run_doctor
from bw.status import run_status

DEFAULT_REGION = "uksouth"

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
    deploy = sub.add_parser("deploy", help="deploy a lab kit into a new tagged resource group")
    deploy.add_argument("lab", help="lab id, e.g. storage-sas-leak")
    deploy.add_argument("--seed", required=True, help="your seed code from the lab page, e.g. K7Q2-MX4P")
    deploy.add_argument("--version", help="kit version from the lab page")
    deploy.add_argument("--sha256", help="kit SHA-256 from the lab page")
    deploy.add_argument("--kit-dir", type=Path, help="use a local kit directory instead of downloading")
    deploy.add_argument("--region", default=DEFAULT_REGION)
    deploy.add_argument("--yes", action="store_true", help="skip the confirmation prompt (for automation)")
    hint = sub.add_parser("hint", help="show the next hint for a lab")
    hint.add_argument("lab")
    hint.add_argument("number", type=int)
    hint.add_argument("--kit-dir", type=Path)
    check = sub.add_parser("check", help="run local practice self-checks (not a verification)")
    check.add_argument("lab")
    check.add_argument("--kit-dir", type=Path)
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

    az = az or Az(out=out, dry_run=args.dry_run)
    try:
        if args.command == "doctor":
            report = run_doctor(az, args.region)
            print_report(report, out)
            return 0 if report.ok else 1
        if args.command == "status":
            return run_status(az, out)
        if args.command == "deploy":
            workdir = kits_home() / f"{args.lab}@{args.version or local}"
            workdir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=str(workdir)) as tmp:
                kit_dir = resolve_kit_dir(args.kit_dir, args.lab, args.version, args.sha256, Path(tmp), out)
                if args.kit_dir is None:
                    final = workdir / args.lab
                    if final.exists():

                        shutil.rmtree(final)
                    kit_dir.rename(final)
                    kit_dir = final
            return run_deploy(az, args.lab, args.seed, kit_dir, args.region, out, confirm, assume_yes=args.yes)
        if args.command == "hint":
            return run_hint(args.lab, args.number, args.kit_dir, out)
        if args.command == "check":
            return run_check(args.lab, args.kit_dir, out)
        if args.command == "cleanup":
            return run_cleanup(az, args.lab, out, confirm, assume_yes=args.yes)
    except AzNotFound as error:
        print(str(error), file=sys.stderr)
        return 127
    except (KitError, DeployError, LintError, InvalidSeed, FileNotFoundError) as error:
        print(f"\nbw: {error}", file=sys.stderr)
        return 1
    except AzError as error:
        print(f"\nAzure CLI error: {error}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 2

if __name__ == "__main__":
    sys.exit(main())
