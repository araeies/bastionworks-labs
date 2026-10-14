"""Obtain a kit, verify it, and unpack it safely (ADR-0016).

Two sources:
- a local kit directory (lab authors, CI kit tests);
- a released kit asset, downloaded by a printed `curl` command and checked against the SHA-256 shown on
  the lab page, a channel independent of GitHub releases. A mismatch aborts before anything is unpacked.
"""

import hashlib
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import List, Optional, TextIO

RELEASE_BASE = "https://github.com/araeies/bastionworks-labs/releases/download"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_LAB_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_KIT_BYTES = 20 * 1024 * 1024
MAX_MEMBERS = 500


class KitError(Exception):
    pass


def kit_asset_url(lab_id: str, version: str) -> str:
    if not _LAB_ID.match(lab_id) or not _VERSION.match(version):
        raise KitError("invalid lab id or version")
    return f"{RELEASE_BASE}/kit-{lab_id}-v{version}/kit-{lab_id}-{version}.tar.gz"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_tool(args: List[str], out: TextIO) -> None:
    """Run a non-az tool (curl, bash), printing it first. Argument list only; no shell."""
    print("$ " + " ".join(shlex.quote(a) for a in args), file=out, flush=True)
    completed = subprocess.run(args, check=False)
    if completed.returncode != 0:
        raise KitError(f"{args[0]} exited with status {completed.returncode}")


def download_kit(lab_id: str, version: str, expected_sha256: str, workdir: Path, out: TextIO) -> Path:
    expected = expected_sha256.strip().lower()
    if not _SHA256.match(expected):
        raise KitError("--sha256 must be the 64-character hex value shown on the lab page")
    if shutil.which("curl") is None:
        raise KitError("curl is required to download kits (it is preinstalled in Azure Cloud Shell)")
    archive = workdir / f"kit-{lab_id}-{version}.tar.gz"
    run_tool(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--proto", "=https", "--tlsv1.2",
         "--max-filesize", str(MAX_KIT_BYTES), "--output", str(archive), kit_asset_url(lab_id, version)],
        out,
    )
    actual = sha256_file(archive)
    if actual != expected:
        archive.unlink()
        raise KitError(f"SHA-256 mismatch: expected {expected}, got {actual}. The kit was NOT unpacked or run.")
    print(f"SHA-256 verified: {actual}", file=out)
    if shutil.which("gh"):
        print("Optional provenance check (needs `gh auth login`):", file=out)
        print(f"  gh attestation verify {shlex.quote(str(archive))} --repo araeies/bastionworks-labs", file=out)
    return archive


def safe_extract(archive: Path, destination: Path) -> Path:
    """Extract only regular files and directories, refusing traversal, absolute paths, links and devices."""
    destination = destination.resolve()
    with tarfile.open(archive, mode="r:gz") as tar:
        members = tar.getmembers()
        if len(members) > MAX_MEMBERS:
            raise KitError("kit archive has too many entries")
        total = 0
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise KitError(f"unsafe path in kit archive: {member.name}")
            if not (member.isfile() or member.isdir()):
                raise KitError(f"kit archive contains a link or special file: {member.name}")
            total += member.size
            if total > MAX_KIT_BYTES:
                raise KitError("kit archive is too large when unpacked")
            target = (destination / member.name).resolve()
            if destination not in target.parents and target != destination:
                raise KitError(f"unsafe path in kit archive: {member.name}")
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise KitError(f"cannot read {member.name}")
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
    roots = [p for p in destination.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise KitError("kit archive must contain exactly one top-level lab directory")
    return roots[0]


def resolve_kit_dir(kit_dir: Optional[Path], lab_id: str, version: Optional[str], sha256: Optional[str],
                    workdir: Path, out: TextIO = sys.stdout) -> Path:
    if kit_dir is not None:
        print(f"Using local kit directory {kit_dir} (no download, no hash check).", file=out)
        return kit_dir
    if not version or not sha256:
        raise KitError("give --version and --sha256 exactly as shown on the lab page (or --kit-dir for a local kit)")
    archive = download_kit(lab_id, version, sha256, workdir, out)
    return safe_extract(archive, workdir / "kit")
