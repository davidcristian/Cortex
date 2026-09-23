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
    """Run git in the test repo, with the same environment the check uses."""
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
    """Write one compose file with several bind mounts."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = "".join(
        f'      - type: bind\n        source: "{source}"\n        target: /at{index}\n'
        for index, source in enumerate(sources)
    )
    path.write_text(f"services:\n  brain:\n    volumes:\n{entries}", encoding="utf-8")
    return path


def test_an_ignored_default_is_accounted_for(repo: Path) -> None:
    _compose(repo, "${CACHE_DIR:-./cache}")
    assert bindcheck.check(repo).faults == []


def test_a_tracked_input_needs_no_ignore_rule(repo: Path) -> None:
    _compose(repo, "./docker/seed.sql", name="docker-compose.yml")
    assert bindcheck.check(repo).faults == []


def test_a_tracked_path_does_not_speak_for_the_other_one(repo: Path) -> None:
    _compose(repo, "./docker/seed.sql")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert "'docker/docker/seed.sql'" in faults[0].detail


def test_an_unignored_default_is_reported_at_both_resolved_paths(repo: Path) -> None:
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo).faults
    assert [fault.line for fault in faults] == [4, 4]
    assert [fault.path for fault in faults] == ["docker/docker-compose.yml"] * 2
    assert "'models'" in faults[0].detail
    assert "'docker/models'" in faults[1].detail


def test_an_ignore_that_only_covers_the_repo_root_still_fails(repo: Path) -> None:
    (repo / ".gitignore").write_text("cache/\n/models/\n", encoding="utf-8")
    _compose(repo, "${MODELS_DIR:-./models}")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert "'docker/models'" in faults[0].detail


def test_a_compose_file_at_the_root_resolves_to_one_path(repo: Path) -> None:
    _compose(repo, "${MODELS_DIR:-./models}", name="docker-compose.yml")
    assert len(bindcheck.check(repo).faults) == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("${MODELS_DIR:-./models}", "./models"),
        ("${MODELS_DIR-./models}", "./models"),
        ('"${MODELS_DIR:-./models}"', "./models"),
        ("./pgdata", "./pgdata"),
        ("${MODELS_DIR}", None),
        ("$MODELS_DIR", None),
    ],
)
def test_default_path_reduces_a_source_to_what_it_takes_with_no_env(
    text: str, expected: str | None
) -> None:
    assert bindcheck.default_path(text) == expected


def test_a_source_it_cannot_reduce_is_refused() -> None:
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


def test_an_escape_that_ends_up_back_inside_from_the_other_project_directory_is_checked(
    repo: Path,
) -> None:
    _compose(repo, "../models")
    faults = bindcheck.check(repo).faults
    assert len(faults) == 1
    assert "'models'" in faults[0].detail


def test_two_project_directories_resolving_to_one_path_are_reported_once(repo: Path) -> None:
    assert bindcheck.resolved_paths(repo, repo / "docker" / "c.yml", "../models") == ["models"]


def test_an_absolute_source_inside_the_tree_is_still_checked(repo: Path) -> None:
    assert bindcheck.resolved_paths(repo, repo / "docker" / "c.yml", str(repo / "models")) == [
        "models"
    ]


def test_a_tree_with_no_compose_file_is_a_failure_not_a_pass(repo: Path) -> None:
    with pytest.raises(bindcheck.ComposeSearchError, match="matched nothing cannot fail"):
        bindcheck.check(repo)


def test_a_compose_file_the_reader_refuses_is_a_refused_file_not_a_finding(repo: Path) -> None:
    (repo / "docker-compose.yml").write_text(
        "services:\n  a:\n    volumes:\n      - type: bind\n        target: /x\n", encoding="utf-8"
    )
    scanned = bindcheck.check(repo)
    assert len(scanned.refused) == 1
    assert scanned.refused[0].line == 0
    assert "declares no source" in scanned.refused[0].detail
    assert scanned.findings == []


def test_a_compose_file_that_is_not_text_is_a_refused_file(repo: Path) -> None:
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    scanned = bindcheck.check(repo)
    assert [(fault.path, fault.line) for fault in scanned.refused] == [("docker-compose.yml", 0)]
    assert scanned.findings == []


def _both(repo: Path) -> None:
    """Write one file the reader cannot decode and one bind default that is not ignored, twice."""
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    _compose(repo, "${MODELS_DIR:-./models}")


def test_a_refused_file_does_not_stop_the_scan(repo: Path) -> None:
    _both(repo)
    scanned = bindcheck.check(repo)
    assert [fault.path for fault in scanned.refused] == ["docker-compose.yml"]
    assert [fault.path for fault in scanned.findings] == ["docker/docker-compose.yml"] * 2
    assert scanned.faults == scanned.refused + scanned.findings


def test_an_unreducible_source_is_an_unasked_mount_on_its_own_line(repo: Path) -> None:
    _compose(repo, "./models/${TIER}")
    scanned = bindcheck.check(repo)
    assert scanned.findings == []
    assert [(fault.line, "cannot reduce" in fault.detail) for fault in scanned.unasked] == [
        (4, True)
    ]
    assert scanned.faults == scanned.unasked


def test_a_git_failure_on_a_mount_is_an_unasked_mount_not_a_finding(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _compose(repo, "${MODELS_DIR:-./models}")
    broken = subprocess.CompletedProcess[bytes](args=[], returncode=128, stdout=b"", stderr=b"boom")

    def _broken(_root: Path, *_args: str) -> subprocess.CompletedProcess[bytes]:
        return broken

    monkeypatch.setattr(bindcheck, "_git", _broken)
    scanned = bindcheck.check(repo)
    assert scanned.findings == []
    assert [fault.detail for fault in scanned.unasked] == ["git ls-files failed for models: boom"]


def test_a_missing_git_is_a_failure(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setenv("GIT_DIR", str(repo / "no-such-git-dir"))
    assert bindcheck.is_tracked(repo, "docker/seed.sql") is True
    assert bindcheck.is_ignored(repo, "cache") is True


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


def test_the_repo_itself_is_clean() -> None:
    assert bindcheck.check(REPO_ROOT).faults == []


def test_the_repo_really_declares_binds_for_this_gate_to_have_checked() -> None:
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


def _counted(repo: Path) -> None:
    """Write two compose files with four bind mounts, three of which resolve into the tree."""
    _binds(repo, ["${CACHE_DIR:-./cache}", "${MODELS_DIR}", "/srv/models"], "docker-compose.yml")
    _binds(repo, ["${CACHE_DIR:-./cache}"], "docker/docker-compose.yml")


def test_check_counts_the_files_binds_and_landings_it_read(repo: Path) -> None:
    _counted(repo)
    scanned = bindcheck.check(repo)
    assert (scanned.files, scanned.mounts, scanned.resolved_paths) == (2, 4, 3)
    assert scanned.faults == []


def test_main_states_what_it_read_beside_the_verdict(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _counted(repo)
    assert bindcheck.main(["--root", str(repo)]) == 0
    assert capsys.readouterr().out == (
        f"bindcheck OK: 4 bind mount(s) under {repo} are outside, tracked, or ignored, "
        f"over 2 compose file(s) and 3 resolved path(s) checked\n"
    )


_REFUSED = (
    "\nbindcheck: 1 compose file(s) could not be read, so no bind in them was checked. Rewrite a "
    "form the reader refuses in one it takes, or save the file as UTF-8 text, as the file's own "
    "fault says.\n"
)
_UNIGNORED = (
    "\nbindcheck: 2 compose bind default(s) resolve to an unignored path in the tree. Point the "
    "default outside the repo, or add the path to .gitignore, unanchored so it matches under "
    "docker/ as well as at the root.\n"
)


_UNASKED = (
    "\nbindcheck: 1 bind mount(s) could not be checked, so git was never asked about their "
    "default. Write the source as a path or as a variable with a default, or fix the git failure "
    "the mount's own fault names.\n"
)


def test_main_counts_an_unreducible_source_apart_from_the_unignored_defaults(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _binds(repo, ["./models/${TIER}", "${MODELS_DIR:-./models}"], "docker/docker-compose.yml")
    assert bindcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("docker/docker-compose.yml:4: cannot reduce source")
    assert captured.out.count("docker/docker-compose.yml:7:") == 2
    assert captured.err == _UNASKED + _UNIGNORED


def test_main_fails_a_run_whose_only_fault_is_an_unasked_mount(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _compose(repo, "./models/${TIER}")
    assert bindcheck.main(["--root", str(repo)]) == 1
    assert capsys.readouterr().err == _UNASKED


def test_main_reports_each_fault_and_exits_one(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _compose(repo, "${MODELS_DIR:-./models}")
    assert bindcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert captured.out.count("docker/docker-compose.yml:4:") == 2
    assert captured.err == _UNIGNORED


def test_main_counts_a_refused_file_as_a_file_and_not_as_a_resolved_path(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    assert bindcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("docker-compose.yml:0: 'utf-8' codec can't decode")
    assert captured.err == _REFUSED


def test_main_counts_every_refused_file(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "docker-compose.yml").write_bytes(b"\xff\xfe not utf-8")
    (repo / "compose.yaml").write_bytes(b"\xff\xfe not utf-8")
    assert bindcheck.main(["--root", str(repo)]) == 1
    assert capsys.readouterr().err == _REFUSED.replace(": 1 compose", ": 2 compose")


def test_main_prints_one_summary_per_kind_when_both_occur(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _both(repo)
    assert bindcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert [line.split(":")[0] for line in captured.out.splitlines()] == [
        "docker-compose.yml",
        "docker/docker-compose.yml",
        "docker/docker-compose.yml",
    ]
    assert captured.err == _REFUSED + _UNIGNORED


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
