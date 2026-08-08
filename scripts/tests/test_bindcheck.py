"""Behaviour of the compose bind-mount gate, over real git repositories.

The rule under test has three verdicts and every one of them is exercised against a real
`git`, because the two questions the gate asks (is this path tracked, is it ignored) are
git's to answer and an emulation of them is the kind of quiet wrongness that leaves a gate
green. The fixtures below therefore `git init` and stage, rather than pretending.
"""

import os
import subprocess
from pathlib import Path

import pytest

import bindcheck

REPO_ROOT = Path(__file__).resolve().parents[2]

BIND = """\
services:
  brain:
    volumes:
      - type: bind
        source: "{source}"
        target: /somewhere
"""


def _env() -> dict[str, str]:
    """The ambient environment without git's own variables.

    Same reason `commitlint.py` strips them: these gates run inside hooks, git exports
    `GIT_DIR` there, and it outranks `-C`, so an inherited one would point the fixture's git
    calls at the real repository this test lives in.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=_env(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo with one ignored output path and one tracked input file."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("cache/\n", encoding="utf-8")
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "seed.sql").write_text("select 1;\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "docker/seed.sql")
    return tmp_path


def _compose(repo: Path, source: str, name: str = "docker/docker-compose.yml") -> Path:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BIND.format(source=source), encoding="utf-8")
    return path


# ── the three verdicts ─────────────────────────────────────────────────────────


def test_an_ignored_default_is_accounted_for(repo: Path) -> None:
    """`cache/` is unanchored, so it covers the repo root and `docker/` alike."""
    _compose(repo, "${CACHE_DIR:-./cache}")
    assert bindcheck.check(repo) == []


def test_a_tracked_input_needs_no_ignore_rule(repo: Path) -> None:
    """Not "every default must be gitignored": compose finds an input rather than making one."""
    _compose(repo, "./docker/seed.sql")
    assert bindcheck.check(repo) == []


def test_an_unignored_default_is_reported_at_both_landings(repo: Path) -> None:
    """The whole point: a third default nobody remembered to ignore."""
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo)
    assert [fault.line for fault in faults] == [4, 4]
    assert [fault.path for fault in faults] == ["docker/docker-compose.yml"] * 2
    assert "'models'" in faults[0].detail
    assert "'docker/models'" in faults[1].detail


def test_an_ignore_that_only_covers_the_repo_root_still_fails(repo: Path) -> None:
    """An anchored rule misses the bare `docker compose -f docker/...` project directory."""
    (repo / ".gitignore").write_text("cache/\n/models/\n", encoding="utf-8")
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo)
    assert len(faults) == 1
    assert "'docker/models'" in faults[0].detail


def test_a_compose_file_at_the_root_has_one_landing(repo: Path) -> None:
    _compose(repo, "${MODELS_DIR:-./models}", name="docker-compose.yml")
    assert len(bindcheck.check(repo)) == 1


# ── which sources the gate has an opinion about ────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("${MODELS_DIR:-./models}", "./models"),
        ("${MODELS_DIR-./models}", "./models"),
        ('"${MODELS_DIR:-./models}"', "./models"),
        ("./pgdata", "./pgdata"),
        ("${MODELS_DIR}", None),  # wholly env-supplied: the user's own disk
        ("$MODELS_DIR", None),
    ],
)
def test_default_path_reduces_a_source_to_what_it_takes_with_no_env(
    text: str, expected: str | None
) -> None:
    assert bindcheck.default_path(text) == expected


def test_a_source_it_cannot_reduce_is_refused() -> None:
    """Fail closed: an expansion mid-path is a guess this scan will not make."""
    with pytest.raises(bindcheck.BindCheckError, match="cannot reduce"):
        bindcheck.default_path("./models/${TIER}")


def test_an_env_only_source_is_nobody_elses_business(repo: Path) -> None:
    _compose(repo, "${MODELS_DIR}")
    assert bindcheck.check(repo) == []


def test_a_path_outside_the_tree_is_nobody_elses_business(repo: Path) -> None:
    _compose(repo, "/srv/models")
    assert bindcheck.check(repo) == []


def test_a_relative_escape_out_of_the_tree_is_ignored(repo: Path) -> None:
    _compose(repo, "../models", name="docker-compose.yml")
    assert bindcheck.check(repo) == []


def test_an_escape_that_lands_back_inside_from_the_other_project_directory_is_checked(
    repo: Path,
) -> None:
    """`../models` beside `docker/` is outside the tree; beside the repo root it is `models`."""
    _compose(repo, "../models")
    faults = bindcheck.check(repo)
    assert len(faults) == 1
    assert "'models'" in faults[0].detail


def test_two_project_directories_landing_on_one_path_are_reported_once(repo: Path) -> None:
    """`docker/../models` and `./models` are the same directory and deserve one complaint."""
    assert bindcheck.landings(repo, repo / "docker" / "c.yml", "../models") == ["models"]


def test_an_absolute_source_inside_the_tree_is_still_checked(repo: Path) -> None:
    assert bindcheck.landings(repo, repo / "docker" / "c.yml", str(repo / "models")) == ["models"]


# ── failing closed ─────────────────────────────────────────────────────────────


def test_a_tree_with_no_compose_file_is_a_failure_not_a_pass(repo: Path) -> None:
    """A scan whose glob matched nothing reporting OK is the defect this gate exists to avoid."""
    with pytest.raises(bindcheck.BindCheckError, match="matched nothing cannot fail"):
        bindcheck.check(repo)


def test_a_compose_file_the_reader_refuses_is_a_fault(repo: Path) -> None:
    (repo / "docker-compose.yml").write_text(
        "services:\n  a:\n    volumes:\n      - type: bind\n        target: /x\n", encoding="utf-8"
    )
    faults = bindcheck.check(repo)
    assert len(faults) == 1
    assert faults[0].line == 0
    assert "declares no source" in faults[0].detail


def test_a_compose_file_that_is_not_text_is_a_fault(repo: Path) -> None:
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    faults = bindcheck.check(repo)
    assert len(faults) == 1
    assert faults[0].line == 0


def test_an_unreducible_source_is_a_fault_on_its_own_line(repo: Path) -> None:
    _compose(repo, "./models/${TIER}")
    faults = bindcheck.check(repo)
    assert len(faults) == 1
    assert faults[0].line == 4
    assert "cannot reduce" in faults[0].detail


def test_a_missing_git_is_a_failure(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without git the gate cannot answer either question, so it refuses rather than passes."""

    def _no_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        message = "no git here"
        raise OSError(message)

    monkeypatch.setattr(subprocess, "run", _no_git)
    with pytest.raises(bindcheck.BindCheckError, match="cannot run git"):
        bindcheck.is_tracked(repo, "models")


def test_a_git_that_answers_neither_yes_nor_no_is_a_failure(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = subprocess.CompletedProcess[bytes](args=[], returncode=128, stdout=b"", stderr=b"boom")

    def _broken(_root: Path, *_args: str) -> subprocess.CompletedProcess[bytes]:
        return broken

    monkeypatch.setattr(bindcheck, "_git", _broken)
    with pytest.raises(bindcheck.BindCheckError, match="git ls-files failed"):
        bindcheck.is_tracked(repo, "models")
    with pytest.raises(bindcheck.BindCheckError, match="git check-ignore failed"):
        bindcheck.is_ignored(repo, "models")


# ── which files are scanned ────────────────────────────────────────────────────


def test_both_stems_and_both_suffixes_count(repo: Path) -> None:
    _compose(repo, "${A:-./one}", name="compose.yaml")
    _compose(repo, "${B:-./two}", name="docker/docker-compose.gpu.yml")
    names = {path.name for path in bindcheck.compose_files(repo)}
    assert names == {"compose.yaml", "docker-compose.gpu.yml"}


def test_an_unrelated_yaml_file_is_not_a_compose_file(repo: Path) -> None:
    _compose(repo, "${A:-./cache}")
    (repo / "action.yml").write_text("name: not compose\n", encoding="utf-8")
    assert [path.name for path in bindcheck.compose_files(repo)] == ["docker-compose.yml"]


def test_vendored_trees_are_not_scanned(repo: Path) -> None:
    _compose(repo, "${A:-./cache}")
    _compose(repo, "${B:-./models}", name="node_modules/pkg/docker-compose.yml")
    assert [path.name for path in bindcheck.compose_files(repo)] == ["docker-compose.yml"]
    assert bindcheck.check(repo) == []


def test_a_dangling_symlink_is_skipped(repo: Path) -> None:
    _compose(repo, "${A:-./cache}")
    (repo / "docker-compose.gone.yml").symlink_to(repo / "nowhere.yml")
    assert [path.name for path in bindcheck.compose_files(repo)] == ["docker-compose.yml"]


# ── the repo this gate guards, and the CLI ─────────────────────────────────────


def test_the_repo_itself_is_clean() -> None:
    """The gate's own assertion, run as a test so `check-scripts` catches drift too."""
    assert bindcheck.check(REPO_ROOT) == []


def test_the_repo_really_declares_binds_for_this_gate_to_have_checked() -> None:
    """A guard on the guard: zero mounts read would make the test above vacuously green."""
    mounts = [
        mount
        for compose in bindcheck.compose_files(REPO_ROOT)
        for mount in bindcheck.read_mounts(compose.read_text(encoding="utf-8"))
    ]
    defaults = [mount for mount in mounts if "${" in mount.source]
    assert len(defaults) >= 6, mounts


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert bindcheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "bindcheck OK" in capsys.readouterr().out


def test_main_reports_each_fault_and_exits_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _compose(repo, "${MODELS_DIR:-./models}")
    assert bindcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert captured.out.count("docker/docker-compose.yml:4:") == 2
    assert "2 compose bind default(s)" in captured.err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope"
    assert bindcheck.main(["--root", str(missing)]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_reports_a_scan_that_could_not_run(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bindcheck.main(["--root", str(repo)]) == 2
    assert "no compose file" in capsys.readouterr().err
