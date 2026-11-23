import subprocess
from pathlib import Path

import pytest

import homecheck
from gitenv import git_env

# Built from parts so this file passes the check it tests.
HOME = "/home/"
DASHED = "-home-"


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git(root: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(root), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=git_env(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    return tmp_path


@pytest.mark.parametrize(
    ("line", "names"),
    [
        (f"logs in `{HOME}alice/run/`", ["alice"]),
        (f"cd {HOME}alice", ["alice"]),
        (f"see file://{HOME}alice/a.png", ["alice"]),
        (f"`/tmp/claude-1000/{DASHED}alice-Files-Git-Cortex/abc/scratchpad/`", ["alice"]),
        (f"{HOME}alice.smith/notes", ["alice.smith"]),
        (f"{HOME}bob/x and {HOME}carol/y", ["bob", "carol"]),
    ],
)
def test_a_home_directory_in_either_form_is_found(line: str, names: list[str]) -> None:
    assert homecheck.home_names(line) == names


@pytest.mark.parametrize(
    "line",
    [
        f"ls {HOME}user/Documents",
        f"bind cortex-home:{HOME}cortex",
        f'"HOME": "{HOME}nobody"',
        f"file://{HOME}u/Shot.png and {HOME}me/todo",
        f"a file {HOME}a.png under the root",
        f"https://example.com{HOME}alice/page",
        "./home/alice/ is relative",
        f"`/tmp/claude-1000/{DASHED}user-Files/`",
        "work-from-home-office-hours",
        "--home-dir-flag",
        f"the form {HOME}<name>/ and {DASHED}<name>-",
        "",
    ],
)
def test_a_placeholder_or_a_path_that_is_no_home_directory_is_not_found(line: str) -> None:
    assert homecheck.home_names(line) == []


def test_scan_text_reports_each_name_with_its_line() -> None:
    text = f"clean\n{HOME}alice/a and {DASHED}bob-x\n"
    assert homecheck.scan_text(Path("f.md"), text) == [
        homecheck.Violation(path=Path("f.md"), line=2, name="alice"),
        homecheck.Violation(path=Path("f.md"), line=2, name="bob"),
    ]


def test_scan_skips_binary_and_ignored_files(repo: Path) -> None:
    _write(repo, ".gitignore", "out/\nlocal.md\n")
    _write(repo, "out/run.md", f"{HOME}alice/x\n")
    _write(repo, "local.md", f"{HOME}alice/x\n")
    (repo / "blob.bin").write_bytes(b"\x00" + f"{HOME}alice/x".encode())
    _write(repo, "docs/a.md", f"{HOME}bob/x\n")
    scanned = homecheck.scan(repo)
    assert scanned.files == 2
    assert scanned.violations == [homecheck.Violation(path=Path("docs/a.md"), line=1, name="bob")]


def test_main_fails_and_names_the_line(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "a.md", f"one\n{DASHED}alice-Files\n")
    assert homecheck.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert "a.md:2: home directory alice" in captured.out
    assert "1 home directory name(s) found" in captured.err


def test_main_passes_a_clean_tree(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "a.md", f"{HOME}user/notes\n")
    assert homecheck.main(["--root", str(repo)]) == 0
    assert "homecheck OK: 1 text file(s)" in capsys.readouterr().out


def test_a_tree_with_no_text_file_is_a_failure(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "blob.bin").write_bytes(b"\x00")
    assert homecheck.main(["--root", str(repo)]) == 2
    assert "read nothing" in capsys.readouterr().err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert homecheck.main(["--root", str(tmp_path / "missing")]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_a_root_git_cannot_answer_about_is_a_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "a.md", "text\n")
    assert homecheck.main(["--root", str(tmp_path)]) == 2
    assert "git cannot say" in capsys.readouterr().err


def test_main_defaults_to_the_current_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "a.md", f"{HOME}alice/x\n")
    monkeypatch.chdir(repo)
    assert homecheck.main([]) == 1


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_committed_tree_names_no_home_directory(capsys: pytest.CaptureFixture[str]) -> None:
    assert homecheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "homecheck OK:" in capsys.readouterr().out


def test_the_walk_reads_the_tree_and_the_placeholder_paths_it_writes() -> None:
    assert homecheck.scan(REPO_ROOT).files >= 1000
    claims = REPO_ROOT / "brain" / "packages" / "core" / "tests" / "test_file_claim.py"
    text = claims.read_text(encoding="utf-8")
    assert {match.group(1) for match in homecheck.HOME_PATH.finditer(text)} == {"user"}
