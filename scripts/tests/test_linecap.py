# The autouse fixture below is called by pytest, never by name, which pyright cannot see.
# pyright: reportUnusedFunction=false

from pathlib import Path

import pytest

import backlogindex
import linecap
from linecap import Exemption

REPO_ROOT = Path(__file__).resolve().parents[2]
EXEMPTIONS = linecap.EXEMPTIONS
MARKER = "<!-- generated -->"


@pytest.fixture(autouse=True)
def _without_exemptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linecap, "EXEMPTIONS", ())


def write_file(path: Path, lines: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n" * lines, encoding="utf-8")


def write_document(root: Path, lines: int = 3) -> None:
    """Write the one markdown file `main` needs, since it fails when it reads none."""
    write_file(root / "docs" / "adr" / "ADR-0001-first.md", lines)


def test_scan_reports_files_over_cap_in_walk_order(tmp_path: Path) -> None:
    write_file(tmp_path / "big.py", 11)
    write_file(tmp_path / "ok.py", 10)
    write_file(tmp_path / "nested" / "huge.rs", 12)
    violations = linecap.scan(tmp_path, cap=10).violations
    assert violations == [
        linecap.Violation(path=Path("big.py"), lines=11, cap=10),
        linecap.Violation(path=Path("nested/huge.rs"), lines=12, cap=10),
    ]


def test_scan_clean_tree_returns_nothing(tmp_path: Path) -> None:
    write_file(tmp_path / "small.py", 3)
    assert linecap.scan(tmp_path, cap=10).violations == []


def test_scan_cap_boundary_allows_exactly_cap_lines(tmp_path: Path) -> None:
    write_file(tmp_path / "at_cap.py", 300)
    write_file(tmp_path / "over_cap.py", 301)
    violations = linecap.scan(tmp_path, cap=300).violations
    assert violations == [linecap.Violation(path=Path("over_cap.py"), lines=301, cap=300)]


def test_scan_counts_comments_and_blank_lines(tmp_path: Path) -> None:
    (tmp_path / "mixed.py").write_text("# comment\n\nvalue = 1\n", encoding="utf-8")
    violations = linecap.scan(tmp_path, cap=2).violations
    assert violations == [linecap.Violation(path=Path("mixed.py"), lines=3, cap=2)]


@pytest.mark.parametrize("name", ["big.ts", "big.tsx"])
def test_scan_caps_overlay_typescript(tmp_path: Path, name: str) -> None:
    write_file(tmp_path / "app" / "src" / name, 50)
    violations = linecap.scan(tmp_path, cap=10).violations
    assert violations == [linecap.Violation(path=Path("app/src") / name, lines=50, cap=10)]


def test_scan_caps_ambient_declaration_files(tmp_path: Path) -> None:
    write_file(tmp_path / "shims.d.ts", 50)
    violations = linecap.scan(tmp_path, cap=10).violations
    assert violations == [linecap.Violation(path=Path("shims.d.ts"), lines=50, cap=10)]


def test_scan_ignores_files_that_are_neither_source_nor_markdown(tmp_path: Path) -> None:
    write_file(tmp_path / "notes.txt", 50)
    write_file(tmp_path / "data.json", 50)
    assert linecap.scan(tmp_path, cap=10, document_cap=10).violations == []


def test_scan_ignores_stylesheets_markup_and_the_proto(tmp_path: Path) -> None:
    write_file(tmp_path / "overlay.css", 50)
    write_file(tmp_path / "index.html", 50)
    write_file(tmp_path / "body.proto", 50)
    assert linecap.scan(tmp_path, cap=10).violations == []


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
    assert linecap.scan(tmp_path, cap=10).violations == []


@pytest.mark.parametrize("name", ["attestation.py", "latest.ts", "Contest.tsx", "testable.ts"])
def test_scan_does_not_skip_files_that_merely_contain_test(tmp_path: Path, name: str) -> None:
    write_file(tmp_path / name, 50)
    violations = linecap.scan(tmp_path, cap=10).violations
    assert violations == [linecap.Violation(path=Path(name), lines=50, cap=10)]


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
    assert linecap.scan(tmp_path, cap=10).violations == []


def test_scan_skips_exempt_directory_components_at_any_depth(tmp_path: Path) -> None:
    write_file(tmp_path / "crate" / "tests" / "deep" / "big.rs", 50)
    write_file(tmp_path / "crate" / "src" / "big.rs", 50)
    violations = linecap.scan(tmp_path, cap=10).violations
    assert violations == [linecap.Violation(path=Path("crate/src/big.rs"), lines=50, cap=10)]


def test_scan_skips_dangling_symlink(tmp_path: Path) -> None:
    write_file(tmp_path / "ok.py", 3)
    (tmp_path / ".#routing.py").symlink_to(tmp_path / "routing.py")
    assert linecap.scan(tmp_path, cap=10).violations == []


def test_scan_caps_a_decision_record_at_the_document_cap(tmp_path: Path) -> None:
    write_file(tmp_path / "docs" / "adr" / "ADR-0001-at-cap.md", 250)
    write_file(tmp_path / "docs" / "adr" / "ADR-0002-over-cap.md", 251)
    violations = linecap.scan(tmp_path, cap=300, document_cap=250).violations
    assert violations == [
        linecap.Violation(path=Path("docs/adr/ADR-0002-over-cap.md"), lines=251, cap=250)
    ]


def test_scan_caps_a_readings_record_at_the_document_cap(tmp_path: Path) -> None:
    write_file(tmp_path / "docs" / "readings" / "model-swap.md", 21)
    write_file(tmp_path / "docs" / "readings" / "prompt-cache.md", 20)
    violations = linecap.scan(tmp_path, cap=10, document_cap=20).violations
    assert violations == [
        linecap.Violation(path=Path("docs/readings/model-swap.md"), lines=21, cap=20)
    ]


@pytest.mark.parametrize(
    "relative",
    [
        "README.md",
        "docs/adr/README.md",
        "docs/adr/adr-0001-lowercase.md",
        "docs/modules/long.md",
        "docs/refinements/tasks/001-a-task.md",
        "brain/packages/core/notes.md",
    ],
)
def test_scan_caps_every_other_markdown_file(tmp_path: Path, relative: str) -> None:
    write_file(tmp_path / relative, 11)
    violations = linecap.scan(tmp_path, cap=300, document_cap=10).violations
    assert violations == [linecap.Violation(path=Path(relative), lines=11, cap=10)]


def test_each_rule_reports_the_cap_that_applies_to_the_file(tmp_path: Path) -> None:
    write_file(tmp_path / "big.py", 15)
    write_file(tmp_path / "docs" / "adr" / "ADR-0001-big.md", 15)
    write_file(tmp_path / "docs" / "readings" / "small.md", 12)
    violations = linecap.scan(tmp_path, cap=10, document_cap=14).violations
    assert violations == [
        linecap.Violation(path=Path("big.py"), lines=15, cap=10),
        linecap.Violation(path=Path("docs/adr/ADR-0001-big.md"), lines=15, cap=14),
    ]


def test_an_exempt_document_is_neither_capped_nor_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = tmp_path / "docs" / "refinements" / "index.md"
    index.parent.mkdir(parents=True)
    index.write_text(MARKER + "\nx\n" * 400, encoding="utf-8")
    write_document(tmp_path)
    monkeypatch.setattr(
        linecap, "EXEMPTIONS", (Exemption("docs/refinements/index.md", MARKER, "a tool writes it"),)
    )
    scanned = linecap.scan(tmp_path, cap=10, document_cap=10)
    assert (scanned.documents, scanned.violations) == (linecap.Tally(files=1, lines=3), [])


def test_an_exemption_for_a_file_that_is_gone_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "ok.py", 3)
    write_document(tmp_path)
    monkeypatch.setattr(linecap, "EXEMPTIONS", (Exemption("gone.md", MARKER, "a tool writes it"),))
    assert linecap.main(["--root", str(tmp_path)]) == 2
    assert "the exemption for gone.md names a file that cannot be read" in capsys.readouterr().err


def test_an_exemption_for_a_document_no_longer_generated_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "ok.py", 3)
    write_document(tmp_path)
    write_file(tmp_path / "index.md", 400)
    monkeypatch.setattr(linecap, "EXEMPTIONS", (Exemption("index.md", MARKER, "a tool writes it"),))
    assert linecap.main(["--root", str(tmp_path)]) == 2
    assert "but the file does not contain" in capsys.readouterr().err


def test_this_repositorys_exemptions_all_name_a_generated_index() -> None:
    covered = linecap.exempt_documents(REPO_ROOT, EXEMPTIONS)
    assert covered == frozenset(Path(item.path) for item in EXEMPTIONS)
    assert all(item.marker == backlogindex.BEGIN for item in EXEMPTIONS)


def test_the_cli_passes_over_this_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(linecap, "EXEMPTIONS", EXEMPTIONS)
    assert linecap.main(["--root", str(REPO_ROOT)]) == 0
    assert "linecap OK:" in capsys.readouterr().out


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
    write_document(tmp_path, lines=21)
    exit_code = linecap.main(
        ["--root", str(tmp_path), "--max-lines", "10", "--document-max-lines", "20"]
    )
    assert exit_code == 1
    assert capsys.readouterr().out == (
        "big.py: 11 lines (cap 10)\ndocs/adr/ADR-0001-first.md: 21 lines (cap 20)\n"
    )


def test_main_prints_summary_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "ok.py", 7)
    write_document(tmp_path, lines=3)
    write_file(tmp_path / "docs" / "readings" / "one.md", 5)
    exit_code = linecap.main(
        ["--root", str(tmp_path), "--max-lines", "10", "--document-max-lines", "20"]
    )
    assert exit_code == 0
    expected = (
        f"linecap OK: 1 non-test source file(s) under {tmp_path} are within 10 lines, "
        f"over 7 line(s) counted\n"
        f"linecap OK: 2 markdown file(s) under {tmp_path} are within 20 lines, "
        f"over 8 line(s) counted\n"
    )
    assert capsys.readouterr().out == expected


def test_scan_counts_what_it_measured_and_not_what_it_walked_past(tmp_path: Path) -> None:
    write_file(tmp_path / "one.py", 3)
    write_file(tmp_path / "nested" / "two.rs", 5)
    write_file(tmp_path / "test_three.py", 400)
    write_file(tmp_path / "notes.txt", 400)
    write_file(tmp_path / "tests" / "four.py", 400)
    write_file(tmp_path / "docs" / "adr" / "ADR-0001-five.md", 4)
    write_file(tmp_path / "docs" / "readings" / "six.md", 6)
    scanned = linecap.scan(tmp_path, cap=10)
    assert scanned.sources == linecap.Tally(files=2, lines=8)
    assert scanned.documents == linecap.Tally(files=2, lines=10)
    assert scanned.violations == []


def test_a_tree_with_no_source_file_is_a_failure_not_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "test_only.py", 400)
    write_document(tmp_path)
    assert linecap.main(["--root", str(tmp_path), "--max-lines", "10"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"linecap: no non-test source file under {tmp_path}; a scan that read nothing cannot fail\n"
    )


def test_a_tree_with_no_markdown_file_is_the_same_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_file(tmp_path / "ok.py", 7)
    write_file(tmp_path / "notes.txt", 400)
    assert linecap.main(["--root", str(tmp_path), "--max-lines", "10"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"linecap: no markdown file under {tmp_path}; a scan that read nothing cannot fail\n"
    )


def test_an_empty_tree_is_the_same_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert linecap.main(["--root", str(tmp_path)]) == 2
    assert "a scan that read nothing cannot fail" in capsys.readouterr().err


def test_main_defaults_to_cwd_and_caps_300_and_250(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_file(tmp_path / "big.py", 301)
    write_file(tmp_path / "ok.py", 300)
    write_document(tmp_path, lines=251)
    write_file(tmp_path / "docs" / "readings" / "ok.md", 250)
    monkeypatch.chdir(tmp_path)
    exit_code = linecap.main([])
    assert exit_code == 1
    assert capsys.readouterr().out == (
        "big.py: 301 lines (cap 300)\ndocs/adr/ADR-0001-first.md: 251 lines (cap 250)\n"
    )


def test_main_rejects_missing_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "absent"
    exit_code = linecap.main(["--root", str(missing)])
    assert exit_code == 2
    assert capsys.readouterr().err == f"linecap: root {missing} is not a directory\n"
