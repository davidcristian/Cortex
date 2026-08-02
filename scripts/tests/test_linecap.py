from pathlib import Path

import pytest

import dashcheck
import linecap


def write_file(path: Path, lines: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n" * lines, encoding="utf-8")


def test_scan_reports_files_over_cap_in_walk_order(tmp_path: Path) -> None:
    write_file(tmp_path / "big.py", 11)
    write_file(tmp_path / "ok.py", 10)
    write_file(tmp_path / "nested" / "huge.rs", 12)
    violations = linecap.scan(tmp_path, cap=10)
    assert violations == [
        linecap.Violation(path=Path("big.py"), lines=11),
        linecap.Violation(path=Path("nested/huge.rs"), lines=12),
    ]


def test_scan_clean_tree_returns_nothing(tmp_path: Path) -> None:
    write_file(tmp_path / "small.py", 3)
    assert linecap.scan(tmp_path, cap=10) == []


def test_scan_cap_boundary_allows_exactly_cap_lines(tmp_path: Path) -> None:
    write_file(tmp_path / "at_cap.py", 300)
    write_file(tmp_path / "over_cap.py", 301)
    violations = linecap.scan(tmp_path, cap=300)
    assert violations == [linecap.Violation(path=Path("over_cap.py"), lines=301)]


def test_scan_counts_comments_and_blank_lines(tmp_path: Path) -> None:
    (tmp_path / "mixed.py").write_text("# comment\n\nvalue = 1\n", encoding="utf-8")
    violations = linecap.scan(tmp_path, cap=2)
    assert violations == [linecap.Violation(path=Path("mixed.py"), lines=3)]


@pytest.mark.parametrize("name", ["big.ts", "big.tsx"])
def test_scan_caps_overlay_typescript(tmp_path: Path, name: str) -> None:
    write_file(tmp_path / "app" / "src" / name, 50)
    violations = linecap.scan(tmp_path, cap=10)
    assert violations == [linecap.Violation(path=Path("app/src") / name, lines=50)]


def test_scan_caps_ambient_declaration_files(tmp_path: Path) -> None:
    """`.d.ts` is hand-written TypeScript, so it is capped like any other `.ts`."""
    write_file(tmp_path / "shims.d.ts", 50)
    violations = linecap.scan(tmp_path, cap=10)
    assert violations == [linecap.Violation(path=Path("shims.d.ts"), lines=50)]


def test_scan_ignores_non_source_suffixes(tmp_path: Path) -> None:
    write_file(tmp_path / "notes.txt", 50)
    write_file(tmp_path / "README.md", 50)
    assert linecap.scan(tmp_path, cap=10) == []


def test_scan_ignores_stylesheets_markup_and_the_proto(tmp_path: Path) -> None:
    """The three uncapped file kinds, pinned so dropping one is a deliberate edit here."""
    write_file(tmp_path / "overlay.css", 50)
    write_file(tmp_path / "index.html", 50)
    write_file(tmp_path / "body.proto", 50)
    assert linecap.scan(tmp_path, cap=10) == []


@pytest.mark.parametrize(
    "name",
    [
        "test_big.py",
        "big_test.py",
        "conftest.py",
        "big_test.rs",
        "big.test.ts",
        "big.test.tsx",
        "test-setup.ts",
    ],
)
def test_scan_skips_test_named_files(tmp_path: Path, name: str) -> None:
    write_file(tmp_path / name, 50)
    assert linecap.scan(tmp_path, cap=10) == []


@pytest.mark.parametrize("name", ["attestation.py", "latest.ts", "Contest.tsx", "testable.ts"])
def test_scan_does_not_skip_files_that_merely_contain_test(tmp_path: Path, name: str) -> None:
    write_file(tmp_path / name, 50)
    violations = linecap.scan(tmp_path, cap=10)
    assert violations == [linecap.Violation(path=Path(name), lines=50)]


@pytest.mark.parametrize(
    "directory",
    [
        ".git",
        ".venv",
        ".claude",
        "target",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "coverage",
        "tests",
        "_generated",
    ],
)
def test_scan_skips_exempt_directories(tmp_path: Path, directory: str) -> None:
    write_file(tmp_path / directory / "big.py", 50)
    write_file(tmp_path / directory / "big.ts", 50)
    assert linecap.scan(tmp_path, cap=10) == []


def test_skipped_dirs_match_dashcheck_plus_tests_and_generated() -> None:
    """docs/modules/repo-gates.md states this relationship; a drift here falsifies that doc."""
    only_linecap = linecap.SKIPPED_DIRS - dashcheck.SKIPPED_DIRS
    only_dashcheck = dashcheck.SKIPPED_DIRS - linecap.SKIPPED_DIRS
    assert only_linecap == {"tests", "_generated"}
    assert only_dashcheck == set()


def test_scan_skips_exempt_directory_components_at_any_depth(tmp_path: Path) -> None:
    write_file(tmp_path / "crate" / "tests" / "deep" / "big.rs", 50)
    write_file(tmp_path / "crate" / "src" / "big.rs", 50)
    violations = linecap.scan(tmp_path, cap=10)
    assert violations == [linecap.Violation(path=Path("crate/src/big.rs"), lines=50)]


def test_scan_skips_dangling_symlink(tmp_path: Path) -> None:
    write_file(tmp_path / "ok.py", 3)
    (tmp_path / ".#routing.py").symlink_to(tmp_path / "routing.py")
    assert linecap.scan(tmp_path, cap=10) == []


def test_scan_raises_typed_error_for_unreadable_file(tmp_path: Path) -> None:
    locked = tmp_path / "locked.py"
    write_file(locked, 5)
    locked.chmod(0o000)
    try:
        with pytest.raises(linecap.UnreadableFileError, match=f"cannot read {locked}"):
            linecap.scan(tmp_path, cap=10)
    finally:
        locked.chmod(0o600)


def test_main_reports_unreadable_file_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = tmp_path / "locked.py"
    write_file(locked, 5)
    locked.chmod(0o000)
    try:
        exit_code = linecap.main(["--root", str(tmp_path)])
    finally:
        locked.chmod(0o600)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"linecap: cannot read {locked}: ")


def test_main_prints_violations_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "big.py", 11)
    exit_code = linecap.main(["--root", str(tmp_path), "--max-lines", "10"])
    assert exit_code == 1
    assert capsys.readouterr().out == "big.py: 11 lines (cap 10)\n"


def test_main_prints_summary_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "ok.py", 10)
    exit_code = linecap.main(["--root", str(tmp_path), "--max-lines", "10"])
    assert exit_code == 0
    expected = f"linecap OK: no non-test source file under {tmp_path} exceeds 10 lines\n"
    assert capsys.readouterr().out == expected


def test_main_defaults_to_cwd_and_cap_300(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_file(tmp_path / "big.py", 301)
    monkeypatch.chdir(tmp_path)
    exit_code = linecap.main([])
    assert exit_code == 1
    assert capsys.readouterr().out == "big.py: 301 lines (cap 300)\n"


def test_main_rejects_missing_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "absent"
    exit_code = linecap.main(["--root", str(missing)])
    assert exit_code == 2
    assert capsys.readouterr().err == f"linecap: root {missing} is not a directory\n"
