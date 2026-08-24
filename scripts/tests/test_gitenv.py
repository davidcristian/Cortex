"""Behaviour of the environment every git call in this tree runs with.

The failure this guards is silent by construction: a call that inherits `GIT_DIR` answers about
the wrong repository, correctly and without a word. So the assertions here are about what is
absent from the mapping, and the three gate suites each pin the same fact end to end, against a
real `git` with a bogus `GIT_DIR` exported over it. The last test here is about the caller that
does not exist yet, which is the one a shared helper cannot help by existing.
"""

import os
from pathlib import Path

import pytest

import gitenv

GATES = Path(__file__).resolve().parents[1]
# How a git call is spelled in this tree, gate and fixture alike: a fixed argv, no shell.
ARGV_HEAD = '["git", '


def test_every_variable_git_exports_to_a_hook_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not `GIT_DIR` alone: each of these redirects part of the answer a gate asks for.

    The prefix is spelled out rather than read from the module, so that widening it is a red
    here rather than a test that agrees with whatever the module now means.
    """
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(name, "/somewhere/else")
    assert [key for key in gitenv.git_env() if key.startswith("GIT_")] == []


def test_the_rest_of_the_environment_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gate still needs a PATH to find git on, and a runner's own variables are not git's.

    `GITHUB_ACTIONS` is the reason the prefix carries its underscore: dropping everything that
    starts `GIT` would take a CI runner's whole environment with it.
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
    """The ordinary case, where the strip is a copy: outside a hook there is nothing to drop."""
    monkeypatch.setattr(os, "environ", {"PATH": "/usr/bin", "HOME": "/home/nobody"})
    assert gitenv.git_env() == {"PATH": "/usr/bin", "HOME": "/home/nobody"}


def test_every_file_that_runs_git_reads_this_environment() -> None:
    """The trigger this module was written for is the next caller, not the three that exist.

    A gate or a fixture that builds its own environment is wrong in silence, so the obligation is
    structural rather than remembered: a file here that spells a git argv must also spell the call
    that hands it one. The three gates are named as a floor, since a scan that matched nothing
    would report this forever.
    """
    sources = {
        path.relative_to(GATES).as_posix(): path.read_text(encoding="utf-8")
        for path in [*GATES.glob("*.py"), *GATES.glob("tests/*.py")]
    }
    callers = {name for name, text in sources.items() if ARGV_HEAD in text}
    assert {"bindcheck.py", "commitlint.py", "dashcheck.py"} <= callers
    assert [name for name in sorted(callers) if "git_env(" not in sources[name]] == []
