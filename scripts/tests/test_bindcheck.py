"""Tests for the compose bind-mount gate, run against real git repositories.

The rule under test has three verdicts, and each one is exercised against a real `git`, because
the two questions the gate asks (is this path tracked, is it ignored) are git's to answer, and an
emulation of them could be wrong on a case no test covers. The fixtures below therefore run
`git init` and stage files.
"""

import subprocess
from pathlib import Path

import pytest

import bindcheck
from gitenv import git_env

REPO_ROOT = Path(__file__).resolve().parents[2]

BIND = """\
services:
  brain:
    volumes:
      - type: bind
        source: "{source}"
        target: /somewhere
"""


def _git(repo: Path, *args: str) -> None:
    """Drive git against the fixture's own tree, with the environment the gate itself uses.

    Uses `gitenv.git_env()` rather than building the environment here, because an inherited
    `GIT_DIR` outranks `-C`: a fixture that forgot to strip it would stage into the real
    repository this test lives in.
    """
    subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=git_env(),
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


def _binds(repo: Path, sources: list[str], name: str) -> Path:
    """One compose file declaring several binds, for counting what a walk read."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = "".join(
        f'      - type: bind\n        source: "{source}"\n        target: /at{index}\n'
        for index, source in enumerate(sources)
    )
    path.write_text(f"services:\n  brain:\n    volumes:\n{entries}", encoding="utf-8")
    return path


# ── the three verdicts ─────────────────────────────────────────────────────────


def test_an_ignored_default_is_accounted_for(repo: Path) -> None:
    """`cache/` is unanchored, so it covers the repo root and `docker/` alike."""
    _compose(repo, "${CACHE_DIR:-./cache}")
    assert bindcheck.check(repo).faults == []


def test_a_tracked_input_needs_no_ignore_rule(repo: Path) -> None:
    """A bind onto a file the repo tracks passes, since compose reads that input rather than
    creating it."""
    _compose(repo, "./docker/seed.sql", name="docker-compose.yml")
    assert bindcheck.check(repo).faults == []


def test_a_tracked_landing_does_not_speak_for_the_other_one(repo: Path) -> None:
    """The exemption applies per landing rather than per mount.

    The same source under the `docker/` project directory resolves to `docker/docker/seed.sql`,
    where the repo ships nothing, so that landing is a directory a compose run creates. Reading
    the tracked landing as the answer for both landings once left that one unreported.
    """
    _compose(repo, "./docker/seed.sql")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert "'docker/docker/seed.sql'" in faults[0].detail


def test_an_unignored_default_is_reported_at_both_landings(repo: Path) -> None:
    """A default that is neither tracked nor ignored is reported at each landing it resolves to.

    This is the case the gate exists to catch: a compose run creates the directory, and git then
    takes it into the index.
    """
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo).faults
    assert [fault.line for fault in faults] == [4, 4]
    assert [fault.path for fault in faults] == ["docker/docker-compose.yml"] * 2
    assert "'models'" in faults[0].detail
    assert "'docker/models'" in faults[1].detail


def test_an_ignore_that_only_covers_the_repo_root_still_fails(repo: Path) -> None:
    """An anchored rule misses the bare `docker compose -f docker/...` project directory."""
    (repo / ".gitignore").write_text("cache/\n/models/\n", encoding="utf-8")
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert "'docker/models'" in faults[0].detail


def test_a_compose_file_at_the_root_has_one_landing(repo: Path) -> None:
    _compose(repo, "${MODELS_DIR:-./models}", name="docker-compose.yml")
    assert len(bindcheck.check(repo).faults) == 1


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
    assert bindcheck.check(repo).faults == []


def test_a_path_outside_the_tree_is_nobody_elses_business(repo: Path) -> None:
    _compose(repo, "/srv/models")
    assert bindcheck.check(repo).faults == []


def test_a_relative_escape_out_of_the_tree_is_ignored(repo: Path) -> None:
    _compose(repo, "../models", name="docker-compose.yml")
    assert bindcheck.check(repo).faults == []


def test_an_escape_that_lands_back_inside_from_the_other_project_directory_is_checked(
    repo: Path,
) -> None:
    """`../models` beside `docker/` is outside the tree; beside the repo root it is `models`."""
    _compose(repo, "../models")
    faults = bindcheck.check(repo).faults
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
    with pytest.raises(bindcheck.ComposeSearchError, match="matched nothing cannot fail"):
        bindcheck.check(repo)


def test_a_compose_file_the_reader_refuses_is_a_fault(repo: Path) -> None:
    (repo / "docker-compose.yml").write_text(
        "services:\n  a:\n    volumes:\n      - type: bind\n        target: /x\n", encoding="utf-8"
    )
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert faults[0].line == 0
    assert "declares no source" in faults[0].detail


def test_a_compose_file_that_is_not_text_is_a_fault(repo: Path) -> None:
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert faults[0].line == 0


def test_an_unreducible_source_is_a_fault_on_its_own_line(repo: Path) -> None:
    _compose(repo, "./models/${TIER}")
    faults = bindcheck.check(repo).faults
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


def test_an_exported_git_dir_does_not_decide_which_repository_answers(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The strip is what makes `-C` the answer, and both questions here depend on it.

    Git exports GIT_DIR to every hook it runs, and `just check` runs this gate from one.
    Pointed at anything that is not a repository, an inherited GIT_DIR makes both calls fatal,
    so the gate fails on a tree whose binds are all accounted for. Every gate that asks git
    anything has this test.
    """
    monkeypatch.setenv("GIT_DIR", str(repo / "no-such-git-dir"))
    assert bindcheck.is_tracked(repo, "docker/seed.sql") is True
    assert bindcheck.is_ignored(repo, "cache") is True


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
    assert bindcheck.check(repo).faults == []


def test_a_dangling_symlink_is_skipped(repo: Path) -> None:
    _compose(repo, "${A:-./cache}")
    (repo / "docker-compose.gone.yml").symlink_to(repo / "nowhere.yml")
    assert [path.name for path in bindcheck.compose_files(repo)] == ["docker-compose.yml"]


# ── the repo this gate guards, and the CLI ─────────────────────────────────────


def test_the_repo_itself_is_clean() -> None:
    """The gate's own assertion, run as a test so `check-scripts` catches drift too."""
    assert bindcheck.check(REPO_ROOT).faults == []


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


# ── what the walk read ─────────────────────────────────────────────────────────


def _counted(repo: Path) -> None:
    """Two files, four binds, three landings: three different numbers, none derivable."""
    _binds(repo, ["${CACHE_DIR:-./cache}", "${MODELS_DIR}", "/srv/models"], "docker-compose.yml")
    _binds(repo, ["${CACHE_DIR:-./cache}"], "docker/docker-compose.yml")


def test_check_counts_the_files_binds_and_landings_it_read(repo: Path) -> None:
    """Landings are neither the mounts nor twice them: env-only asks nowhere, the root asks once."""
    _counted(repo)
    scanned = bindcheck.check(repo)
    assert (scanned.files, scanned.mounts, scanned.landings) == (2, 4, 3)
    assert scanned.faults == []


def test_main_states_what_it_read_beside_the_verdict(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _counted(repo)
    assert bindcheck.main(["--root", str(repo)]) == 0
    assert capsys.readouterr().out == (
        f"bindcheck OK: 4 bind mount(s) under {repo} are outside, tracked, or ignored, "
        f"over 2 compose file(s) and 3 landing(s) checked\n"
    )


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
