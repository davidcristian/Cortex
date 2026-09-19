import subprocess
from collections.abc import Sequence
from pathlib import Path

from assertedlines import suite_of
from backloganchors import MARKDOWN
from composefiles import COMPOSE_STEMS, COMPOSE_SUFFIXES
from gitenv import git_env
from linecap import EXTRA_SKIPS, SOURCE_SUFFIXES, is_skipped_file
from logcalls import PYTHON, modules
from samplecheck import runbooks
from skippeddirs import SKIPPED_DIRS
from treewalk import walk_files

GATES = Path(__file__).resolve().parents[1]
REPO_ROOT = GATES.parent
# A tracked directory containing none of the names below, so the answer comes from the
# ignore rules and not from what happens to exist here.
PROBE = "brain/packages/core"
# The two names git does not ignore everywhere they appear, so the repo's ignore rules
# cannot replace this list.
NOT_RESTATEMENTS = {".git", "coverage"}


def _ignored_anywhere(name: str) -> bool:
    """Whether git ignores a directory of this name wherever it appears in this repo."""
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
    """Every file under ``directory`` the line cap, anchor scan or compose walk reads."""
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


def _read_by_a_scoped_reader() -> list[Path]:
    """Every file the three readers limited to a subtree would open."""
    brain = list(modules(REPO_ROOT))
    found = [module for module, _, _ in brain]
    found.extend(runbooks(REPO_ROOT))
    for suite in sorted({suite_of(shown) for _, _, shown in brain}):
        tree = REPO_ROOT / suite
        if tree.is_dir():
            found.extend(path for path in walk_files(tree) if path.suffix == PYTHON)
    return found


def _read_by_a_gate(directory: Path, scoped: Sequence[Path]) -> list[Path]:
    """Every file under ``directory`` that any of the six readers with a selection would open."""
    inside = {path for path in scoped if directory in path.parents}
    return sorted(set(_read_by_a_suffix_walk(directory)) | inside)


def test_no_tree_git_ignores_and_this_list_misses_holds_a_file_a_walk_reads() -> None:
    scoped = _read_by_a_scoped_reader()
    reachable = {
        directory.relative_to(REPO_ROOT): [
            path.relative_to(REPO_ROOT) for path in _read_by_a_gate(directory, scoped)
        ]
        for directory in _ignored_directories()
        if not any(part in SKIPPED_DIRS for part in directory.relative_to(REPO_ROOT).parts)
    }
    assert {name: files for name, files in reachable.items() if files} == {}
