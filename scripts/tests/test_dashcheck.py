from pathlib import Path

import pytest

import dashcheck

# Built from escapes, not literals, so this file passes the gate it tests.
EM = "\u2014"
EN = "\u2013"
MINUS = "\u2212"


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── what counts as punctuation ─────────────────────────────────────────────────


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
        "a 2-4B model fits the budget",  # a range takes a plain hyphen
        "0.15-0.27 GB of VRAM",
        f"24 GB {MINUS} ~11 GB of headroom",  # minus sign: arithmetic, still legal
        "# noqa: DTZ001 -- the naive value under test",  # the inline-reason idiom
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


# ── scanning text ──────────────────────────────────────────────────────────────


def test_scan_text_reports_line_numbers_and_content() -> None:
    text = f"clean line\nbad {EM} line\nclean again\n"
    (violation,) = dashcheck.scan_text(Path("f.md"), text)
    assert violation.line == 2
    assert violation.kind == "em dash"
    assert violation.text == f"bad {EM} line"


def test_scan_text_reports_every_offending_line() -> None:
    assert len(dashcheck.scan_text(Path("f.md"), f"a {EM} b\nc {EM} d\n")) == 2


# ── binary handling ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"plain text", False),
        (b"\x89PNG\x00\x1a", True),  # null byte
        (b"\xff\xfe\xfa", True),  # not valid UTF-8
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
    path.symlink_to(tmp_path / "missing.txt")  # dangling symlink
    with pytest.raises(dashcheck.UnreadableFileError):
        dashcheck.read_text(path)


# ── walking a tree ─────────────────────────────────────────────────────────────


def test_scan_finds_violations_across_file_types(tmp_path: Path) -> None:
    _write(tmp_path, "doc.md", f"prose {EM} here\n")
    _write(tmp_path, "src/app.ts", f"// comment {EM} here\n")
    _write(tmp_path, "clean.py", "x = 1\n")
    found = {v.path.name for v in dashcheck.scan(tmp_path)}
    assert found == {"doc.md", "app.ts"}


def test_scan_skips_excluded_directories(tmp_path: Path) -> None:
    _write(tmp_path, "node_modules/pkg/index.js", f"a {EM} b\n")
    _write(tmp_path, "target/debug/out.rs", f"a {EM} b\n")
    _write(tmp_path, ".git/COMMIT_EDITMSG", f"a {EM} b\n")
    assert dashcheck.scan(tmp_path) == []


def test_scan_skips_binary_files(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\x00\xff")
    assert dashcheck.scan(tmp_path) == []


def test_scan_skips_non_regular_files(tmp_path: Path) -> None:
    (tmp_path / "dangling").symlink_to(tmp_path / "nowhere")
    assert dashcheck.scan(tmp_path) == []


# ── the CLI ────────────────────────────────────────────────────────────────────


def test_main_passes_a_clean_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "doc.md", "clean prose\n")
    assert dashcheck.main(["--root", str(tmp_path)]) == 0
    assert "dashcheck OK" in capsys.readouterr().out


def test_main_fails_and_names_the_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "doc.md", f"bad {EM} line\n")
    assert dashcheck.main(["--root", str(tmp_path)]) == 1
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "doc.md", "x\n")

    def boom(_path: Path) -> str:
        message = "cannot read doc.md: nope"
        raise dashcheck.UnreadableFileError(message)

    monkeypatch.setattr(dashcheck, "read_text", boom)
    assert dashcheck.main(["--root", str(tmp_path)]) == 2
    assert "cannot read doc.md" in capsys.readouterr().err


def test_main_defaults_to_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "doc.md", "clean\n")
    monkeypatch.chdir(tmp_path)
    assert dashcheck.main([]) == 0
