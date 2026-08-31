"""Tests for the environment every git call in this tree runs with.

A call that inherits `GIT_DIR` answers about the wrong repository and reports no error, so these
assertions are about what `git_env()` removes from the mapping rather than what it keeps. The
last test covers the callers that do not exist yet: a shared helper only helps if every file that
runs git actually uses it.
"""

import os
from pathlib import Path

import pytest

import gitenv

GATES = Path(__file__).resolve().parents[1]
# A git call here is always a fixed argv with no shell, so this literal prefix finds every one.
ARGV_HEAD = '["git", '


def test_every_variable_git_exports_to_a_hook_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """All four `GIT_*` variables git exports to a hook are dropped, not `GIT_DIR` alone.

    Each of them redirects part of the answer a gate asks git for. The prefix is written out here
    rather than read from the module, so widening the module's prefix fails this test instead of
    being restated by it.
    """
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(name, "/somewhere/else")
    assert [key for key in gitenv.git_env() if key.startswith("GIT_")] == []


def test_the_rest_of_the_environment_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables outside the `GIT_` prefix survive, including `PATH` and `GITHUB_ACTIONS`.

    A gate needs `PATH` to find git at all. `GITHUB_ACTIONS` is why the prefix carries its
    underscore: dropping every name starting `GIT` would take a CI runner's own variables too.
    """
    monkeypatch.setenv("GIT_DIR", "/somewhere/else")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("PATH", os.environ["PATH"])
    stripped = gitenv.git_env()
    assert stripped["GITHUB_ACTIONS"] == "true"
    assert stripped["PATH"] == os.environ["PATH"]


def test_an_environment_git_never_touched_is_returned_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside a hook there is nothing to drop, so the environment is returned unchanged."""
    monkeypatch.setattr(os, "environ", {"PATH": "/usr/bin", "HOME": "/home/nobody"})
    assert gitenv.git_env() == {"PATH": "/usr/bin", "HOME": "/home/nobody"}


def test_every_file_that_runs_git_reads_this_environment() -> None:
    """Every file under `scripts/` that spells a git argv also calls `git_env()`.

    A gate or fixture that builds its own environment fails silently, so this is checked
    structurally rather than left to be remembered when the next caller is written. The three
    named gates are a floor: without them a scan that matched no files would pass forever.
    """
    sources = {
        path.relative_to(GATES).as_posix(): path.read_text(encoding="utf-8")
        for path in [*GATES.glob("*.py"), *GATES.glob("tests/*.py")]
    }
    callers = {name for name, text in sources.items() if ARGV_HEAD in text}
    assert {"bindcheck.py", "commitlint.py", "dashcheck.py"} <= callers
    assert [name for name in sorted(callers) if "git_env(" not in sources[name]] == []
