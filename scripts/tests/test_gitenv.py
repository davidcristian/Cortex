import os
from pathlib import Path

import pytest

import gitenv
import moduleconstants
import scriptcalls

SCRIPTS = Path(__file__).resolve().parents[1]
SHARED = "git_env"
# The files that run git today. This is a minimum, not the whole set: a scan that found
# nothing would otherwise pass, and a caller added later is checked without being listed.
CALLERS = frozenset(
    {
        "bindcheck.py",
        "commitlint.py",
        "dashcheck.py",
        "tests/test_bindcheck.py",
        "tests/test_commitlint.py",
        "tests/test_dashcheck.py",
        "tests/test_skippeddirs.py",
    }
)


def test_every_variable_git_exports_to_a_hook_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(name, "/somewhere/else")
    assert [key for key in gitenv.git_env() if key.startswith("GIT_")] == []


def test_the_rest_of_the_environment_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/somewhere/else")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("PATH", os.environ["PATH"])
    stripped = gitenv.git_env()
    assert stripped["GITHUB_ACTIONS"] == "true"
    assert stripped["PATH"] == os.environ["PATH"]


def test_an_environment_git_never_touched_is_returned_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "environ", {"PATH": "/usr/bin", "HOME": "/home/nobody"})
    assert gitenv.git_env() == {"PATH": "/usr/bin", "HOME": "/home/nobody"}


def test_every_git_call_here_is_handed_this_environment() -> None:
    calls = {
        path.relative_to(SCRIPTS).as_posix(): scriptcalls.git_calls(
            moduleconstants.parse(path, path.name)
        )
        for path in [*SCRIPTS.glob("*.py"), *SCRIPTS.glob("tests/*.py")]
    }
    assert {name for name, found in calls.items() if found} >= CALLERS
    assert [
        f"{name}:{call.line}"
        for name, found in sorted(calls.items())
        for call in found
        if call.environment != SHARED
    ] == []
