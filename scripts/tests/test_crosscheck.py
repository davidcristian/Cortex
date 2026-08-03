from pathlib import Path

import pytest

import crosscheck

REPO_ROOT = Path(__file__).resolve().parents[2]

BYTE_CEILING = crosscheck.Constant(
    label="a ceiling",
    why="the two enforcers must agree",
    sites=(
        crosscheck.Site("body.rs", "MAX_CAPTURE_BYTES"),
        crosscheck.Site("brain.py", "MAX_IMAGE_BYTES"),
    ),
)


def _tie(root: Path, rust: str, python: str) -> None:
    """Write the two-file tree `BYTE_CEILING` names, one declaration per language."""
    declaration = f"pub const MAX_CAPTURE_BYTES: usize = {rust};\n"
    (root / "body.rs").write_text(declaration, encoding="utf-8")
    (root / "brain.py").write_text(f"MAX_IMAGE_BYTES = {python}\n", encoding="utf-8")


# ── reducing a right-hand side to a comparable value ───────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("6 * 1024 * 1024", 6291456),
        ("6291456", 6291456),
        ("6_291_456", 6291456),
        ("  6*1024*1024  ", 6291456),
        ("6291456  # the same number, spelled out", 6291456),
        ('"x-cortex-seam-token"', "x-cortex-seam-token"),
        ('"x-cortex-seam-token"  # noqa: S105', "x-cortex-seam-token"),
        ('""', ""),
    ],
)
def test_parse_value_reduces_both_forms(text: str, expected: str | int) -> None:
    """The point of reducing rather than comparing text: two spellings of one number tie."""
    assert crosscheck.parse_value(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        '"unterminated',  # a lone opening quote
        '"a" + "b"',  # more than one literal
        r'"a\tb"',  # an escape this reducer will not decode
        "6 + 1024",  # arithmetic beyond a product
        "SOME_OTHER_CONST",  # an alias, not a literal
        "1600.0",  # not an integer
        "",  # an empty right-hand side
    ],
)
def test_parse_value_refuses_what_it_cannot_reduce(text: str) -> None:
    """Fail closed: a form the reducer does not understand is a fault, never a guess."""
    with pytest.raises(crosscheck.CrossCheckError):
        crosscheck.parse_value(text)


# ── finding a declaration in each language ─────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("decl.rs", "pub const MAX_CAPTURE_BYTES: usize = 6 * 1024 * 1024;"),
        ("decl.rs", "const MAX_CAPTURE_BYTES: usize = 6291456;"),
        ("decl.rs", "pub(crate) const MAX_CAPTURE_BYTES: usize = 6291456;"),
        ("decl.rs", "    static MAX_CAPTURE_BYTES: usize = 6291456;"),
        ("decl.rs", "pub const MAX_CAPTURE_BYTES: usize = 6291456; // trailing"),
        ("decl.py", "MAX_CAPTURE_BYTES = 6 * 1024 * 1024"),
        ("decl.py", "MAX_CAPTURE_BYTES: int = 6291456"),
        ("decl.py", "MAX_CAPTURE_BYTES = 6291456  # a trailing comment"),
        ("decl.ts", "const MAX_CAPTURE_BYTES = 6291456;"),
        ("decl.ts", "export const MAX_CAPTURE_BYTES = 6 * 1024 * 1024;"),
        ("decl.ts", "export const MAX_CAPTURE_BYTES: number = 6291456;"),
        ("decl.ts", "const MAX_CAPTURE_BYTES = 6291456; // a trailing comment"),
    ],
)
def test_read_value_reads_each_declaration_form(tmp_path: Path, name: str, line: str) -> None:
    (tmp_path / name).write_text(f"# preamble\n{line}\nafter = 1\n", encoding="utf-8")
    site = crosscheck.Site(name, "MAX_CAPTURE_BYTES")
    assert crosscheck.read_value(tmp_path, site) == 6291456


def test_read_value_ties_a_string_across_both_languages(tmp_path: Path) -> None:
    """The seam token's real shape: a Rust `&str` const against a Python one with a noqa."""
    rust = 'const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";\n'
    python = 'SEAM_TOKEN_HEADER = "x-cortex-seam-token"  # noqa: S105 - the header NAME\n'
    (tmp_path / "auth.rs").write_text(rust, encoding="utf-8")
    (tmp_path / "seam.py").write_text(python, encoding="utf-8")
    from_rust = crosscheck.read_value(tmp_path, crosscheck.Site("auth.rs", "SEAM_TOKEN_HEADER"))
    from_python = crosscheck.read_value(tmp_path, crosscheck.Site("seam.py", "SEAM_TOKEN_HEADER"))
    assert from_rust == from_python == "x-cortex-seam-token"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("decl.rs", "pub const MAX_CAPTURE_BYTES_EXTRA: usize = 1;\n"),
        ("decl.py", "MAX_CAPTURE_BYTES_EXTRA = 1\n"),
        ("decl.py", "    MAX_CAPTURE_BYTES = 1\n"),  # indented: a local, not a module constant
        ("decl.rs", "let MAX_CAPTURE_BYTES: usize = 1;\n"),  # a binding, not a const item
        ("decl.ts", "const MAX_CAPTURE_BYTES_EXTRA = 1;\n"),
        ("decl.ts", "  const MAX_CAPTURE_BYTES = 1;\n"),  # indented: a local, not a module one
        ("decl.ts", "let MAX_CAPTURE_BYTES = 1;\n"),  # reassignable, so not a constant
    ],
)
def test_read_value_fails_closed_when_the_name_is_gone(
    tmp_path: Path, name: str, text: str
) -> None:
    """A rename must break the gate loudly; a near miss must not be mistaken for the real one."""
    (tmp_path / name).write_text(text, encoding="utf-8")
    site = crosscheck.Site(name, "MAX_CAPTURE_BYTES")
    with pytest.raises(crosscheck.CrossCheckError, match="declares no MAX_CAPTURE_BYTES"):
        crosscheck.read_value(tmp_path, site)


def test_read_value_fails_closed_on_two_declarations(tmp_path: Path) -> None:
    """Two matches means the scan cannot say which one the other tree is tied to."""
    (tmp_path / "decl.py").write_text("A = 1\nA = 2\n", encoding="utf-8")
    with pytest.raises(crosscheck.CrossCheckError, match="declares A 2 times"):
        crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "A"))


def test_read_value_fails_closed_on_a_missing_file(tmp_path: Path) -> None:
    site = crosscheck.Site("moved/away.py", "A")
    with pytest.raises(crosscheck.CrossCheckError, match=r"cannot read moved/away\.py"):
        crosscheck.read_value(tmp_path, site)


def test_read_value_fails_closed_on_a_non_utf8_file(tmp_path: Path) -> None:
    (tmp_path / "decl.py").write_bytes(b"A = \xff\xfe\n")
    with pytest.raises(crosscheck.CrossCheckError, match=r"cannot read decl\.py"):
        crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "A"))


def test_read_value_fails_closed_on_an_unknown_language(tmp_path: Path) -> None:
    (tmp_path / "decl.go").write_text("const A = 1\n", encoding="utf-8")
    with pytest.raises(crosscheck.CrossCheckError, match="no declaration syntax is known"):
        crosscheck.read_value(tmp_path, crosscheck.Site("decl.go", "A"))


def test_read_value_ties_a_number_from_typescript_to_python(tmp_path: Path) -> None:
    """The session-title bound's real shape: a bare overlay `const` against a bare Python name."""
    (tmp_path / "sessionState.ts").write_text("const TITLE_MAX = 48;\n", encoding="utf-8")
    (tmp_path / "sessions.py").write_text("TITLE_MAX = 48\n", encoding="utf-8")
    from_ts = crosscheck.read_value(tmp_path, crosscheck.Site("sessionState.ts", "TITLE_MAX"))
    from_py = crosscheck.read_value(tmp_path, crosscheck.Site("sessions.py", "TITLE_MAX"))
    assert from_ts == from_py == 48


# ── tying the sites together ───────────────────────────────────────────────────


def test_check_constant_ties_two_spellings_of_one_number(tmp_path: Path) -> None:
    _tie(tmp_path, rust="6 * 1024 * 1024", python="6291456")
    assert crosscheck.check_constant(tmp_path, BYTE_CEILING) == []


def test_check_constant_catches_the_drift_this_gate_exists_for(tmp_path: Path) -> None:
    """One side raised to 8 MiB with its own suite still green is exactly the recorded drift."""
    _tie(tmp_path, rust="8 * 1024 * 1024", python="6 * 1024 * 1024")
    (fault,) = crosscheck.check_constant(tmp_path, BYTE_CEILING)
    assert fault.label == "a ceiling"
    assert "body.rs: MAX_CAPTURE_BYTES = 8388608" in fault.detail
    assert "brain.py: MAX_IMAGE_BYTES = 6291456" in fault.detail
    assert BYTE_CEILING.why in fault.detail


def test_check_constant_reports_a_broken_site_rather_than_agreement(tmp_path: Path) -> None:
    """A site that cannot be read is reported instead of the one remaining value agreeing."""
    (tmp_path / "brain.py").write_text("MAX_IMAGE_BYTES = 6291456\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, BYTE_CEILING)
    assert "cannot read body.rs" in fault.detail


def test_check_constant_reports_every_broken_site(tmp_path: Path) -> None:
    """Both sides named, so one fix does not hide the next one behind it."""
    details = [fault.detail for fault in crosscheck.check_constant(tmp_path, BYTE_CEILING)]
    assert [detail.split(":")[0] for detail in details] == [
        "cannot read body.rs",
        "cannot read brain.py",
    ]


def test_check_constant_refuses_a_registry_entry_that_compares_nothing() -> None:
    """A one-site entry would pass forever, which is a gate that cannot fail."""
    lonely = crosscheck.Constant(
        label="a lonely value",
        why="nothing",
        sites=(crosscheck.Site("brain.py", "A"),),
    )
    (fault,) = crosscheck.check_constant(Path(), lonely)
    assert "fewer than two sites" in fault.detail


def test_check_walks_the_whole_registry(tmp_path: Path) -> None:
    second = BYTE_CEILING._replace(label="another ceiling")
    faults = crosscheck.check(tmp_path, (BYTE_CEILING, second))
    labels = ["a ceiling", "a ceiling", "another ceiling", "another ceiling"]
    assert [fault.label for fault in faults] == labels


# ── the registry, read against the real trees ──────────────────────────────────


def test_the_repo_itself_is_tied() -> None:
    """The gate's own assertion, run as a test so `check-scripts` catches drift too."""
    assert crosscheck.check(REPO_ROOT) == []


def test_every_registered_site_is_in_a_language_the_scan_knows() -> None:
    """A registry entry in an unscanned language would be a silently unenforced coupling."""
    suffixes = {Path(site.path).suffix for c in crosscheck.CONSTANTS for site in c.sites}
    assert suffixes <= set(crosscheck.DECLARATIONS)


def test_every_registered_constant_spans_more_than_one_tree() -> None:
    """A cross-tree gate whose entry sat inside one tree would prove nothing about the seam."""
    for constant in crosscheck.CONSTANTS:
        trees = {site.path.split("/")[0] for site in constant.sites}
        assert len(trees) > 1, constant.label


# ── the CLI ────────────────────────────────────────────────────────────────────


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert crosscheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "crosscheck OK" in capsys.readouterr().out


def test_main_fails_closed_when_no_site_can_be_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty root stands in for every site having moved: loud, never a silent pass."""
    assert crosscheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "the screen-capture byte ceiling: cannot read" in captured.out
    assert "the seam token's metadata key: cannot read" in captured.out
    assert "are not tied" in captured.err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "a-file.md"
    path.write_text("x\n", encoding="utf-8")
    assert crosscheck.main(["--root", str(path)]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_defaults_to_the_current_directory(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(REPO_ROOT)
    assert crosscheck.main([]) == 0
    assert "crosscheck OK" in capsys.readouterr().out
