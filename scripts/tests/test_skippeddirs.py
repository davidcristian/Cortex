"""Tests for the shared directory skip list."""

import subprocess
from pathlib import Path

from backloganchors import MARKDOWN
from composefiles import COMPOSE_STEMS, COMPOSE_SUFFIXES
from gitenv import git_env
from linecap import EXTRA_SKIPS, SOURCE_SUFFIXES, is_skipped_file
from skippeddirs import SKIPPED_DIRS
from treewalk import walk_files

GATES = Path(__file__).resolve().parents[1]
REPO_ROOT = GATES.parent
# A directory git tracks, under which nothing named below exists, so what comes back is the
# ignore rules and not a fact about this checkout.
PROBE = "brain/packages/core"
# The two names git does not ignore everywhere they appear, which is why this list cannot be
# replaced by the repo's ignore rules.
NOT_RESTATEMENTS = {".git", "coverage"}


def _ignored_anywhere(name: str) -> bool:
    """Whether git ignores a directory of this name wherever it appears in this repo.

    The user's own excludes file is disabled, so the answer comes from the repo's `.gitignore`
    files alone and a global rule on one machine cannot change it.
    """
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [  # noqa: S607 -- git on PATH
            "git",
            "-C",
            str(REPO_ROOT),
            "-c",
            "core.excludesFile=/dev/null",
            "check-ignore",
            "-q",
            "--",
            f"{PROBE}/{name}/",
        ],
        capture_output=True,
        check=False,
        env=git_env(),
    )
    assert result.returncode in (0, 1), result.stderr.decode(errors="replace")
    return result.returncode == 0


def test_the_overlap_with_gitignore_is_measured_rather_than_believed() -> None:
    """Nine of the eleven names are also ignored by git everywhere; `.git` and `coverage` are not.
    """
    restatements = {name for name in SKIPPED_DIRS if _ignored_anywhere(name)}
    assert SKIPPED_DIRS - restatements == NOT_RESTATEMENTS
    assert len(restatements) == 9


def _ignored_directories() -> list[Path]:
    """Every directory git ignores that exists in this checkout, as an absolute path."""
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [  # noqa: S607 -- git on PATH
            "git",
            "-C",
            str(REPO_ROOT),
            "-c",
            "core.excludesFile=/dev/null",
            "ls-files",
            "--others",
            "--ignored",
            "--directory",
            "--exclude-standard",
        ],
        capture_output=True,
        check=True,
        env=git_env(),
    )
    listed = (REPO_ROOT / line for line in result.stdout.decode().splitlines())
    return [path for path in listed if path.is_dir()]


def _read_by_a_suffix_walk(directory: Path) -> list[Path]:
    """Every file under ``directory`` that the line cap, the anchor scan or the compose walk reads.

    Each of the three is asked with its own selection rather than a copy of it, and the cap gets
    its own descent because it skips two names the other two do not.
    """
    measured = [
        path
        for path in walk_files(directory, also_skip=EXTRA_SKIPS)
        if path.suffix in SOURCE_SUFFIXES and not is_skipped_file(path.name)
    ]
    prose_and_compose = [
        path
        for path in walk_files(directory)
        if path.suffix == MARKDOWN
        or (path.suffix in COMPOSE_SUFFIXES and path.stem.startswith(COMPOSE_STEMS))
    ]
    return sorted(set(measured) | set(prose_and_compose))


def test_no_tree_git_ignores_and_this_list_misses_holds_a_file_a_walk_reads() -> None:
    """An ignored directory the list does not prune holds nothing the three suffix walks read."""
    reachable = {
        directory.relative_to(REPO_ROOT): [
            path.relative_to(REPO_ROOT) for path in _read_by_a_suffix_walk(directory)
        ]
        for directory in _ignored_directories()
        if not any(part in SKIPPED_DIRS for part in directory.relative_to(REPO_ROOT).parts)
    }
    assert {name: files for name, files in reachable.items() if files} == {}
