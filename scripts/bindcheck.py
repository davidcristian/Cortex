"""Fail when a compose bind mount would create a directory git neither tracks nor ignores."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from composefiles import ComposeSearchError, compose_files, refused_summary
from composemounts import ComposeReadError, Mount, read_mounts, strip_quotes
from gitenv import git_env

_DEFAULTED = re.compile(r"\$\{[A-Za-z_]\w*:?-(?P<default>[^{}]*)\}")
_UNDEFAULTED = re.compile(r"^(?:\$\{[A-Za-z_]\w*\}|\$[A-Za-z_]\w*)$")


class BindCheckError(Exception):
    """A source could not be reduced to a path, or git failed when asked about one."""


class Fault(NamedTuple):
    """One bind mount that is not accounted for, or one compose file the scan could not read."""

    path: str
    line: int
    detail: str


class Scan(NamedTuple):
    """What one walk of the compose files read, and what it could not account for."""

    files: int
    mounts: int
    landings: int
    refused: list[Fault]
    unasked: list[Fault]
    findings: list[Fault]

    @property
    def faults(self) -> list[Fault]:
        """Every fault, unreadable files first, in the order `main` prints them."""
        return self.refused + self.unasked + self.findings


def default_path(source: str) -> str | None:
    """Return the path a source takes with no environment set, or None when env alone decides."""
    text = strip_quotes(source)
    if _UNDEFAULTED.match(text):
        return None
    resolved = _DEFAULTED.sub(lambda match: match.group("default"), text)
    if "$" in resolved:
        msg = f"cannot reduce source {source!r} to a path"
        raise BindCheckError(msg)
    return resolved


def landings(root: Path, compose: Path, path: str) -> list[str]:
    """Return the repo-relative paths one source resolves to, under either project directory."""
    projects = [root] if compose.parent == root else [root, compose.parent]
    found: list[str] = []
    for project in projects:
        landed = Path(path) if Path(path).is_absolute() else Path(os.path.normpath(project / path))
        if root not in landed.parents:
            continue
        relative = landed.relative_to(root).as_posix()
        if relative not in found:
            found.append(relative)
    return found


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run one git command against ``root`` with git's own hook variables stripped."""
    try:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", "-C", str(root), *args],  # noqa: S607 -- git resolves on PATH; an absolute path is not portable
            capture_output=True,
            check=False,
            env=git_env(),
        )
    except OSError as err:
        msg = f"cannot run git: {err}"
        raise BindCheckError(msg) from err


def _failed(result: subprocess.CompletedProcess[bytes], command: str, relative: str) -> str:
    """The message for a git call whose exit code was neither yes nor no."""
    return f"git {command} failed for {relative}: {result.stderr.decode(errors='replace').strip()}"


def is_tracked(root: Path, relative: str) -> bool:
    """Whether git tracks this path, in which case compose finds it rather than creating it."""
    result = _git(root, "ls-files", "--", relative)
    if result.returncode != 0:
        raise BindCheckError(_failed(result, "ls-files", relative))
    return bool(result.stdout.strip())


def is_ignored(root: Path, relative: str) -> bool:
    """Whether git ignores this path, asked with a trailing slash because compose creates one."""
    result = _git(root, "check-ignore", "-q", "--", f"{relative}/")
    if result.returncode not in (0, 1):
        raise BindCheckError(_failed(result, "check-ignore", relative))
    return result.returncode == 0


def _spots(root: Path, compose: Path, mount: Mount) -> tuple[int, list[str]]:
    """How many paths git was asked about for one mount, and which of those it does not know."""
    path = default_path(mount.source)
    if path is None:
        return 0, []
    spots = landings(root, compose, path)
    return len(spots), [
        spot for spot in spots if not is_tracked(root, spot) and not is_ignored(root, spot)
    ]


def check_file(root: Path, compose: Path) -> Scan:
    """Return what one compose file was read for, and every bind source in it not accounted for."""
    name = compose.relative_to(root).as_posix()
    try:
        mounts = read_mounts(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ComposeReadError) as err:
        fault = Fault(path=name, line=0, detail=str(err))
        return Scan(files=1, mounts=0, landings=0, refused=[fault], unasked=[], findings=[])
    asked = 0
    unasked: list[Fault] = []
    faults: list[Fault] = []
    for mount in mounts:
        try:
            count, spots = _spots(root, compose, mount)
        except BindCheckError as err:
            unasked.append(Fault(path=name, line=mount.line, detail=str(err)))
            continue
        asked += count
        faults.extend(
            Fault(
                path=name,
                line=mount.line,
                detail=(
                    f"bind default {mount.source!r} resolves to {spot!r}, which git neither tracks "
                    f"nor ignores; a compose run creates it and `git add -A` stages it"
                ),
            )
            for spot in spots
        )
    return Scan(
        files=1, mounts=len(mounts), landings=asked, refused=[], unasked=unasked, findings=faults
    )


def check(root: Path) -> Scan:
    """Check every compose file under ``root``, in walk order, counting what was read."""
    scans = [check_file(root, compose) for compose in compose_files(root)]
    return Scan(
        files=len(scans),
        mounts=sum(scan.mounts for scan in scans),
        landings=sum(scan.landings for scan in scans),
        refused=[fault for scan in scans for fault in scan.refused],
        unasked=[fault for scan in scans for fault in scan.unasked],
        findings=[fault for scan in scans for fault in scan.findings],
    )


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a compose bind default resolves to an unignored path in the repo.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the compose files (default: current directory)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"bindcheck: root {given} is not a directory", file=sys.stderr)
        return 2
    root = given.resolve()
    try:
        scanned = check(root)
    except (BindCheckError, ComposeSearchError) as err:
        print(f"bindcheck: {err}", file=sys.stderr)
        return 2
    for fault in scanned.faults:
        print(f"{fault.path}:{fault.line}: {fault.detail}")
    if scanned.refused:
        unread = "no bind in them was checked"
        print(refused_summary("bindcheck", len(scanned.refused), unread), file=sys.stderr)
    if scanned.unasked:
        print(
            f"\nbindcheck: {len(scanned.unasked)} bind mount(s) could not be checked, so git was "
            "never asked about their default. Write the source as a path or as a variable with a "
            "default, or fix the git failure the mount's own fault names.",
            file=sys.stderr,
        )
    if scanned.findings:
        print(
            f"\nbindcheck: {len(scanned.findings)} compose bind default(s) resolve to an unignored "
            "path in the tree. Point the default outside the repo, or add the path to .gitignore, "
            "unanchored so it matches under docker/ as well as at the root.",
            file=sys.stderr,
        )
    if scanned.faults:
        return 1
    print(
        f"bindcheck OK: {scanned.mounts} bind mount(s) under {given} are outside, tracked, or "
        f"ignored, over {scanned.files} compose file(s) and {scanned.landings} resolved path(s) "
        "checked"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
