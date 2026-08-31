"""Repo gate: fail when a compose bind mount would materialize an unignored path in the tree.

A `docker compose up` creates a host directory for a bind-mount source that is not there yet,
root-owned and thereafter written from inside the container. Every bind source in this repo names a
relative path, so that directory lands in the working tree, and what a container writes into it is
a multi-gigabyte GGUF or a database dump rather than kilobytes. The only thing between one of those
and a `git add -A` is a `.gitignore` line somebody remembered to write: three such defaults exist
today and all three are matched by three separate acts of remembering.

The rule: every bind-mount source a compose file declares must resolve either outside this repo, or
to a path the repo already tracks, or to a path git ignores. Outside is the user's own disk and none
of the gate's business. Tracked means the repo ships that path as an input, so compose finds it
rather than creating it. Anything else is an output a container writes, and it has to be ignored
before it can be written. The rule is not "every default must be gitignored", which would be false
of `./docker/postgres/init.sql` and of every future bind onto a file the repo carries. The ADR-0026
bind addendum argues it.

Where a relative source lands depends on the project directory, which compose takes from
`--project-directory` when it is given and from the first `-f` file's own directory otherwise. The
`just` recipes pass the repo root; a bare `docker compose -f docker/docker-compose.memory.yml` uses
`docker/`. Both landings are checked, which is why the repo's ignore entries for these paths are
unanchored.

Finding no compose file at all (`composefiles.py` raises on that, for this gate and for
`defaultcheck.py` alike, so the two cannot disagree about which files exist), a mount entry that
cannot be classified (`composemounts.py` raises on those), a source whose expansion cannot be
reduced, and a `git` that cannot be run each fail rather than passing quietly, because a scan whose
glob matched nothing would report success forever.

The success line states what the walk read: compose files, the binds they declare, and the landings
git was actually asked about, which is the count after the env-only sources drop out rather than
before. The floor under it is `composefiles.py`'s, no compose file at all being a failure; the
deeper counts get no floor of their own, since a real compose file may declare no bind at all.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from composefiles import ComposeSearchError, compose_files
from composemounts import ComposeReadError, Mount, read_mounts, strip_quotes
from gitenv import git_env

_DEFAULTED = re.compile(r"\$\{[A-Za-z_]\w*:?-(?P<default>[^{}]*)\}")
_UNDEFAULTED = re.compile(r"^(?:\$\{[A-Za-z_]\w*\}|\$[A-Za-z_]\w*)$")


class BindCheckError(Exception):
    """A source could not be reduced to a path, or git could not answer about one."""


class Fault(NamedTuple):
    """One compose bind that is unaccounted for, or one the scan could not read."""

    path: str
    line: int
    detail: str


class Scan(NamedTuple):
    """One walk of the compose files: what it read, then what it could not account for.

    ``check_file`` returns one of these per file, so the whole walk is their sum. ``landings``
    counts the places git was asked about, which is neither the mounts (an env-only source is
    asked about nowhere) nor twice them (one source can land on one path from both project
    directories, and does whenever the compose file sits at the root).
    """

    files: int
    mounts: int
    landings: int
    faults: list[Fault]


def default_path(source: str) -> str | None:
    """Return the path a source takes with no environment set, or None when env alone decides."""
    text = strip_quotes(source)
    if _UNDEFAULTED.match(text):
        return None  # wholly env-supplied: wherever it points is the user's own disk
    resolved = _DEFAULTED.sub(lambda match: match.group("default"), text)
    if "$" in resolved:
        msg = f"cannot reduce source {source!r} to a path"
        raise BindCheckError(msg)
    return resolved


def landings(root: Path, compose: Path, path: str) -> list[str]:
    """Return the repo-relative paths one source can land on, over both project directories."""
    projects = [root] if compose.parent == root else [root, compose.parent]
    found: list[str] = []
    for project in projects:
        landed = Path(path) if Path(path).is_absolute() else Path(os.path.normpath(project / path))
        if root not in landed.parents:
            continue  # outside the working tree, so nothing of ours can be staged
        relative = landed.relative_to(root).as_posix()
        if relative not in found:
            found.append(relative)
    return found


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run one git command against ``root`` with git's own hook variables stripped.

    The strip is `gitenv.py`'s, which holds the reason for every gate that asks git anything.
    The exit codes stay here, because this gate reads two of them differently, which is why the
    environment is shared and the call is not.
    """
    try:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", "-C", str(root), *args],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=git_env(),
        )
    except OSError as err:
        msg = f"cannot run git: {err}"
        raise BindCheckError(msg) from err


def _failed(result: subprocess.CompletedProcess[bytes], command: str, relative: str) -> str:
    """The message for a git call that answered neither yes nor no."""
    return f"git {command} failed for {relative}: {result.stderr.decode(errors='replace').strip()}"


def is_tracked(root: Path, relative: str) -> bool:
    """Whether the repo ships this path, in which case compose finds it rather than creating it."""
    result = _git(root, "ls-files", "--", relative)
    if result.returncode != 0:
        raise BindCheckError(_failed(result, "ls-files", relative))
    return bool(result.stdout.strip())


def is_ignored(root: Path, relative: str) -> bool:
    """Whether git ignores this path, asked with a trailing slash: compose makes a directory."""
    result = _git(root, "check-ignore", "-q", "--", f"{relative}/")
    if result.returncode not in (0, 1):
        raise BindCheckError(_failed(result, "check-ignore", relative))
    return result.returncode == 0


def _spots(root: Path, compose: Path, mount: Mount) -> tuple[int, list[str]]:
    """How many landings git was asked about for one mount, and which of them it disowned.

    Both questions are asked per landing, never once for the mount. A source can land on an input
    the repo ships under one project directory and on nothing at all under the other, and it is the
    second landing that a compose run creates, so letting the tracked landing answer for both would
    leave that case unreported.
    """
    path = default_path(mount.source)
    if path is None:
        return 0, []
    spots = landings(root, compose, path)
    return len(spots), [
        spot for spot in spots if not is_tracked(root, spot) and not is_ignored(root, spot)
    ]


def check_file(root: Path, compose: Path) -> Scan:
    """Return what one compose file offered the gate, and every unaccounted bind default in it."""
    name = compose.relative_to(root).as_posix()
    try:
        mounts = read_mounts(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ComposeReadError) as err:
        fault = Fault(path=name, line=0, detail=str(err))
        return Scan(files=1, mounts=0, landings=0, faults=[fault])
    asked = 0
    faults: list[Fault] = []
    for mount in mounts:
        try:
            count, spots = _spots(root, compose, mount)
        except BindCheckError as err:
            faults.append(Fault(path=name, line=mount.line, detail=str(err)))
            continue
        asked += count
        faults.extend(
            Fault(
                path=name,
                line=mount.line,
                detail=(
                    f"bind default {mount.source!r} lands on {spot!r}, which git neither tracks "
                    f"nor ignores; a compose run creates it and `git add -A` stages it"
                ),
            )
            for spot in spots
        )
    return Scan(files=1, mounts=len(mounts), landings=asked, faults=faults)


def check(root: Path) -> Scan:
    """Check every compose file under ``root``, in walk order, counting what was read."""
    scans = [check_file(root, compose) for compose in compose_files(root)]
    return Scan(
        files=len(scans),
        mounts=sum(scan.mounts for scan in scans),
        landings=sum(scan.landings for scan in scans),
        faults=[fault for scan in scans for fault in scan.faults],
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a compose bind default lands unignored inside the repo tree.",
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
    faults = scanned.faults
    for fault in faults:
        print(f"{fault.path}:{fault.line}: {fault.detail}")
    if faults:
        print(
            f"\nbindcheck: {len(faults)} compose bind default(s) land unignored in the tree. "
            "Point the default outside the repo, or add the path to .gitignore, unanchored so "
            "it matches under docker/ as well as at the root.",
            file=sys.stderr,
        )
        return 1
    print(
        f"bindcheck OK: {scanned.mounts} bind mount(s) under {given} are outside, tracked, or "
        f"ignored, over {scanned.files} compose file(s) and {scanned.landings} landing(s) checked"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
