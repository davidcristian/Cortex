import subprocess
from pathlib import Path

import pytest

import dashcheck
from gitenv import git_env

# Written as escapes so this file passes the check it tests.
EM = "\u2014"
EN = "\u2013"
MINUS = "\u2212"


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git(root: Path, *args: str) -> None:
    """Run git in the test repo, with the same environment the check uses."""
    subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(root), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=git_env(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Return a real git working tree, because the check reads git's own file list."""
    _git(tmp_path, "init", "-q")
    return tmp_path


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        (f"the cause chained {EM} it fails loud", "em dash"),
        (f"prose with a {EN} spaced en dash in it", "en dash"),
        (f"a 2{EN}4B model, where the range once passed", "en dash"),
    ],
)
def test_punctuating_dashes_are_found(line: str, kind: str) -> None:
    assert dashcheck.find_in_line(line) == kind


@pytest.mark.parametrize(
    "line",
    [
        "a 2-4B model fits the budget",
        "0.15-0.27 GB of VRAM",
        f"24 GB {MINUS} ~11 GB of headroom",
        "# noqa: DTZ001 -- the naive value under test",
        "run cargo build --locked",
        "a well-formed hyphenated-word",
        "",
    ],
)
def test_non_punctuation_is_not_found(line: str) -> None:
    assert dashcheck.find_in_line(line) is None


def test_the_allow_pragma_exempts_a_line() -> None:
    line = f'expected = "a {EM} b"  # {dashcheck.ALLOW_PRAGMA} -- the entity decodes to this'
    assert dashcheck.find_in_line(line) is None


def test_scan_text_reports_line_numbers_and_content() -> None:
    text = f"clean line\nbad {EM} line\nclean again\n"
    (violation,) = dashcheck.scan_text(Path("f.md"), text)
    assert violation.line == 2
    assert violation.kind == "em dash"
    assert violation.text == f"bad {EM} line"


def test_scan_text_reports_every_offending_line() -> None:
    assert len(dashcheck.scan_text(Path("f.md"), f"a {EM} b\nc {EM} d\n")) == 2


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"plain text", False),
        (b"\x89PNG\x00\x1a", True),
        (b"\xff\xfe\xfa", True),
        (f"text {EM} with em dash".encode(), False),
    ],
)
def test_is_binary(data: bytes, expected: bool) -> None:  # noqa: FBT001 -- a parametrized expectation, not a flag
    assert dashcheck.is_binary(data) is expected


def test_read_text_returns_none_for_binary(tmp_path: Path) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(b"\x89PNG\x00")
    assert dashcheck.read_text(path) is None


def test_read_text_raises_on_an_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "gone.txt"
    path.symlink_to(tmp_path / "missing.txt")
    with pytest.raises(dashcheck.UnreadableFileError):
        dashcheck.read_text(path)


def test_scan_finds_violations_across_file_types(repo: Path) -> None:
    _write(repo, "doc.md", f"prose {EM} here\n")
    _write(repo, "src/app.ts", f"// comment {EM} here\n")
    _write(repo, "clean.py", "x = 1\n")
    found = {v.path.name for v in dashcheck.scan(repo).violations}
    assert found == {"doc.md", "app.ts"}


def test_scan_skips_excluded_directories(repo: Path) -> None:
    _write(repo, "node_modules/pkg/index.js", f"a {EM} b\n")
    _write(repo, "target/debug/out.rs", f"a {EM} b\n")
    _write(repo, ".git/COMMIT_EDITMSG", f"a {EM} b\n")
    assert dashcheck.scan(repo).violations == []


def test_scan_skips_binary_files(repo: Path) -> None:
    (repo / "logo.png").write_bytes(b"\x89PNG\x00\xff")
    assert dashcheck.scan(repo).violations == []


def test_scan_skips_non_regular_files(repo: Path) -> None:
    (repo / "dangling").symlink_to(repo / "nowhere")
    assert dashcheck.scan(repo).violations == []


def test_scan_skips_a_file_git_ignores(repo: Path) -> None:
    _write(repo, ".gitignore", "coverage.json\n")
    _write(repo, "coverage.json", f'{{"note": "a {EM} b"}}\n')
    scanned = dashcheck.scan(repo)
    assert scanned.violations == []
    assert scanned.files == 1


def test_scan_never_descends_into_a_directory_git_ignores(repo: Path) -> None:
    _write(repo, ".gitignore", "blobs/\n")
    _write(repo, "blobs/deep/note.md", f"a {EM} b\n")
    scanned = dashcheck.scan(repo)
    assert scanned.violations == []
    assert scanned.files == 1


@pytest.mark.parametrize("staged", [False, True])
def test_a_file_the_repo_does_not_ship_yet_is_still_read(repo: Path, staged: bool) -> None:  # noqa: FBT001 -- a parametrized case, not a flag
    _write(repo, "doc.md", f"fresh {EM} prose\n")
    if staged:
        _git(repo, "add", "doc.md")
    (violation,) = dashcheck.scan(repo).violations
    assert violation.path == Path("doc.md")


def test_an_exported_git_dir_does_not_decide_which_repository_answers(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, ".gitignore", "out/\n")
    _write(repo, "out/generated.md", f"generated {EM} prose\n")
    _write(repo, "doc.md", "clean prose\n")
    monkeypatch.setenv("GIT_DIR", str(repo / "no-such-git-dir"))
    assert dashcheck.main(["--root", str(repo)]) == 0


def test_a_root_git_cannot_answer_about_is_a_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "doc.md", "clean prose\n")
    assert dashcheck.main(["--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"git cannot say what {tmp_path} ignores" in captured.err


def test_a_git_that_cannot_be_run_is_a_failure(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        message = "no such executable"
        raise OSError(message)

    monkeypatch.setattr(dashcheck.subprocess, "run", boom)
    assert dashcheck.main(["--root", str(repo)]) == 2
    assert "cannot run git: no such executable" in capsys.readouterr().err


def test_main_passes_a_clean_tree(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "doc.md", "clean prose\n")
    _write(repo, "src/app.ts", "// one\n// two\n")
    assert dashcheck.main(["--root", str(repo)]) == 0
    assert capsys.readouterr().out == (
        f"dashcheck OK: 2 text file(s) under {repo} use no banned dash, over 3 line(s) read\n"
    )


def test_scan_counts_the_text_it_read_and_not_what_it_skipped(repo: Path) -> None:
    _write(repo, ".gitignore", "notes/\n")
    _write(repo, "doc.md", "one\ntwo\n")
    _write(repo, "src/app.ts", "// three\n")
    (repo / "logo.png").write_bytes(b"\x89PNG\x00\xff")
    _write(repo, "node_modules/pkg/index.js", "four\nfive\nsix\n")
    _write(repo, "notes/scratch.md", "seven\neight\n")
    scanned = dashcheck.scan(repo)
    assert (scanned.files, scanned.lines) == (3, 4)
    assert scanned.violations == []


def test_a_tree_with_no_text_file_is_a_failure_not_a_pass(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "logo.png").write_bytes(b"\x89PNG\x00\xff")
    assert dashcheck.main(["--root", str(repo)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"dashcheck: no text file under {repo}; a scan that read nothing cannot fail\n"
    )


def test_a_tree_git_ignores_entirely_meets_the_same_floor(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, ".gitignore", ".gitignore\ndoc.md\n")
    _write(repo, "doc.md", f"an ignored {EM} line\n")
    assert dashcheck.main(["--root", str(repo)]) == 2
    assert "a scan that read nothing cannot fail" in capsys.readouterr().err


def test_main_fails_and_names_the_line(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "doc.md", f"bad {EM} line\n")
    assert dashcheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert f"doc.md:1: em dash: bad {EM} line" in captured.out
    assert dashcheck.ALLOW_PRAGMA in captured.err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, "a-file.md", "x\n")
    assert dashcheck.main(["--root", str(path)]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_reports_an_unreadable_file(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "doc.md", "x\n")

    def boom(_path: Path) -> str:
        message = "cannot read doc.md: nope"
        raise dashcheck.UnreadableFileError(message)

    monkeypatch.setattr(dashcheck, "read_text", boom)
    assert dashcheck.main(["--root", str(repo)]) == 2
    assert "cannot read doc.md" in capsys.readouterr().err


def test_main_defaults_to_the_current_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "doc.md", "clean\n")
    monkeypatch.chdir(repo)
    assert dashcheck.main([]) == 0
