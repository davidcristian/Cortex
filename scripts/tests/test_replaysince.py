import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import replaysince
import scanrecipes
from gitenv import git_env

DAY = "2026-09-19"
BRANCH = "replay"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str, stdin: str = "") -> str:
    """Run git in the test repo, with the same environment the checks use."""
    return subprocess.run(  # noqa: S603 -- fixed argv into a tmp repo, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
        env=git_env(),
    ).stdout


def _commit(subject: str, at: datetime) -> str:
    """Return one `git fast-import` commit on `BRANCH`, committed at `at`."""
    return (
        f"commit refs/heads/{BRANCH}\n"
        f"committer t <t@example.com> {int(at.timestamp())} +0000\n"
        f"data {len(subject)}\n{subject}\n"
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("TZ", "UTC")
    _git(tmp_path, "init", "-q")
    midnight = datetime(2026, 9, 19, tzinfo=UTC)
    stream = "".join(
        [
            _commit("before", midnight - timedelta(seconds=1)),
            _commit("first second", midnight),
            _commit("last second", midnight + timedelta(days=1, seconds=-1)),
        ]
    )
    _git(tmp_path, "fast-import", "--quiet", stdin=stream)
    return tmp_path


def test_a_bare_date_reads_from_midnight() -> None:
    assert replaysince.since_value(DAY) == f"{DAY} 00:00"


@pytest.mark.parametrize("when", [f"{DAY} 05:52", "2026-9-19", f"{DAY}x", "yesterday"])
def test_a_value_that_is_not_a_bare_date_is_kept(when: str) -> None:
    assert replaysince.since_value(when) == when


def test_git_lists_every_commit_of_a_bare_day_whatever_the_hour(repo: Path) -> None:
    listed = _git(repo, "log", BRANCH, f"--since={replaysince.since_value(DAY)}", "--format=%s")
    assert listed.split("\n")[:-1] == ["last second", "first second"]


def test_git_reads_a_kept_time_as_given(repo: Path) -> None:
    listed = _git(
        repo, "log", BRANCH, f"--since={replaysince.since_value(f'{DAY} 12:00')}", "--format=%s"
    )
    assert listed.split("\n")[:-1] == ["last second"]


def test_main_prints_the_value(capsys: pytest.CaptureFixture[str]) -> None:
    assert replaysince.main([DAY]) == 0
    assert capsys.readouterr().out == f"{DAY} 00:00\n"


def test_main_refuses_a_missing_date(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        replaysince.main([])
    assert exited.value.code == 2
    assert "when" in capsys.readouterr().err


def test_every_since_in_the_replay_recipe_is_read_through_the_module() -> None:
    justfile = (REPO_ROOT / scanrecipes.JUSTFILE).read_text(encoding="utf-8")
    reads = [line for line in scanrecipes.recipe_body(justfile, "replay") if "--since=" in line]
    assert len(reads) >= 1
    assert [line for line in reads if "replaysince.py" not in line] == []
