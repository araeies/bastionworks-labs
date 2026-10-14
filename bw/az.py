"""Run Azure CLI commands, printing each one first so learners learn the commands, not the tool (brief §4.1).

bw never opens network connections itself: every Azure interaction goes through `az`, which the learner
can read, rerun or run by hand. No shell is ever involved (argument lists only).
"""

import json
import shlex
import shutil
import subprocess
import sys
from typing import Any, List, Optional, Sequence, TextIO


class AzError(Exception):
    def __init__(self, args: Sequence[str], returncode: int, stderr: str):
        self.args_list = list(args)
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(f"az {' '.join(args[:3])} … failed ({returncode}): {self.stderr.splitlines()[-1] if self.stderr else 'no output'}")


class AzNotFound(Exception):
    """The Azure CLI is not installed or not on PATH."""


def format_command(args: Sequence[str]) -> str:
    return "$ " + " ".join(shlex.quote(a) for a in ["az", *args])


class Az:
    """Thin, printing wrapper over the az CLI. Tests substitute a fake with the same `run` method."""

    def __init__(self, out: TextIO = sys.stdout, dry_run: bool = False, executable: Optional[str] = None):
        self.out = out
        self.dry_run = dry_run
        self.executable = executable or shutil.which("az")

    def run(self, args: List[str], *, mutating: bool = False) -> Any:
        """Print the command, run it, and return parsed JSON (or None for empty output).

        In dry-run mode, mutating commands are printed but not executed; read-only ones still run so the
        plan reflects the real subscription.
        """
        print(format_command(args), file=self.out, flush=True)
        if self.dry_run and mutating:
            print("  (dry run: not executed)", file=self.out)
            return None
        if self.executable is None:
            raise AzNotFound("Azure CLI ('az') not found. Use Azure Cloud Shell, or install it: https://aka.ms/installazurecli")
        completed = subprocess.run(
            [self.executable, *args, "--only-show-errors", "-o", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AzError(args, completed.returncode, completed.stderr)
        output = completed.stdout.strip()
        return json.loads(output) if output else None
