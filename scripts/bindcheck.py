"""Repo gate: fail when a compose bind mount would materialize an unignored path in the tree.

A `docker compose up` creates a host directory for a bind-mount source that is not there
yet, root-owned and thereafter written from inside the container. Every bind source in this
repo names a relative path, so that directory lands in the working tree, and what a container
writes into it is a multi-gigabyte GGUF or a database dump rather than kilobytes. The only
thing between one of those and a `git add -A` is a `.gitignore` line somebody remembered to
write: three such defaults exist today and all three are matched, by three separate acts of
remembering and not by anything that checks. This is that check.

**The rule.** Every bind-mount source a compose file declares must resolve either outside
this repo, or to a path the repo already tracks, or to a path git ignores. Outside is the
user's own disk and none of the gate's business. Tracked means the repo ships that path as an
input, so compose finds it rather than creating it. Anything else is an output a container
writes, and it has to be ignored before it can be written. Note which way that rule runs: it
is not "every default must be gitignored", which would be false of `./docker/postgres/init.sql`
and of every future bind onto a file the repo carries.

**Both landings.** Where a relative source lands depends on the project directory, which
compose takes from `--project-directory` when it is given and from the first `-f` file's own
directory otherwise. The `just` recipes pass the repo root; a bare
`docker compose -f docker/docker-compose.memory.yml` uses `docker/`. Both are checked, which
is why the repo's ignore entries for these paths are deliberately unanchored.

**Fail closed** is the whole point, the same way `crosscheck.py` fails closed. Finding no
compose file at all, a mount entry that cannot be classified (`composemounts.py` refuses
those), a source whose expansion cannot be reduced, and a `git` that cannot be run are each a
failure rather than a quiet pass, because a scan whose glob matched nothing would report
success forever.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from composemounts import ComposeReadError, Mount, read_mounts, strip_quotes

SKIPPED_DIRS = frozenset(
    {".git", ".venv", ".claude", "target", "node_modules", "__pycache__", "dist", "coverage"}
)

# What a compose file is called. Both stems and both suffixes, because a scan that silently
# missed a new override file is the defect this one exists to prevent.
COMPOSE_STEMS = ("docker-compose", "compose")
COMPOSE_SUFFIXES = frozenset({".yml", ".yaml"})

_DEFAULTED = re.compile(r"\$\{[A-Za-z_]\w*:?-(?P<default>[^{}]*)\}")
_UNDEFAULTED = re.compile(r"^(?:\$\{[A-Za-z_]\w*\}|\$[A-Za-z_]\w*)$")


class BindCheckError(Exception):
    """A source could not be reduced to a path, or git could not answer about one."""


class Fault(NamedTuple):
    """One compose bind that is unaccounted for, or one the scan could not read."""

    path: str
    line: int
    detail: str


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
    """Run one git command against ``root`` with git's own hook variables stripped."""
    # These gates run inside hooks, where git exports GIT_DIR, and that variable outranks the
    # -C below: inheriting it would answer about whatever repository git is mid-commit in.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", "-C", str(root), *args],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=env,
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


def _spots(root: Path, compose: Path, mount: Mount) -> list[str]:
    """Every repo-relative landing of one mount that git would have to account for.

    Both questions are asked per landing, never once for the mount. A source can land on an input
    the repo ships under one project directory and on nothing at all under the other, and it is
    the second landing that a compose run creates; letting the tracked one speak for both is the
    same silence this gate exists to remove.
    """
    path = default_path(mount.source)
    if path is None:
        return []
    return [
        spot
        for spot in landings(root, compose, path)
        if not is_tracked(root, spot) and not is_ignored(root, spot)
    ]


def check_file(root: Path, compose: Path) -> list[Fault]:
    """Return every unaccounted bind default in one compose file."""
    name = compose.relative_to(root).as_posix()
    try:
        mounts = read_mounts(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ComposeReadError) as err:
        return [Fault(path=name, line=0, detail=str(err))]
    faults: list[Fault] = []
    for mount in mounts:
        try:
            spots = _spots(root, compose, mount)
        except BindCheckError as err:
            faults.append(Fault(path=name, line=mount.line, detail=str(err)))
            continue
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
    return faults


def compose_files(root: Path) -> list[Path]:
    """Return every compose file under ``root``, refusing to report success on none."""
    found: list[Path] = []
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        found.extend(
            directory / name
            for name in sorted(filenames)
            if Path(name).suffix in COMPOSE_SUFFIXES
            and Path(name).stem.startswith(COMPOSE_STEMS)
            and (directory / name).is_file()
        )
    if not found:
        msg = f"no compose file under {root}; a scan that matched nothing cannot fail"
        raise BindCheckError(msg)
    return found


def check(root: Path) -> list[Fault]:
    """Check every compose file under ``root``, in walk order."""
    return [fault for compose in compose_files(root) for fault in check_file(root, compose)]


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
        faults = check(root)
    except BindCheckError as err:
        print(f"bindcheck: {err}", file=sys.stderr)
        return 2
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
    print(f"bindcheck OK: every compose bind default under {given} is outside, tracked, or ignored")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
