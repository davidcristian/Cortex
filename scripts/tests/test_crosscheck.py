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
    """A one-place entry would pass forever, which is a gate that cannot fail."""
    lonely = crosscheck.Constant(
        label="a lonely value",
        why="nothing",
        sites=(crosscheck.Site("brain.py", "A"),),
    )
    (fault,) = crosscheck.check_constant(Path(), lonely)
    assert "fewer than two places" in fault.detail


def test_check_constant_refuses_an_entry_with_nothing_to_read_the_value_from() -> None:
    """Mentions spend a value; something has to establish it first."""
    mentions_only = crosscheck.Constant(
        label="an unestablished value",
        why="nothing",
        sites=(),
        mentions=(crosscheck.Mention("a.css", "var({value})"), crosscheck.Mention("b.css", "x")),
    )
    (fault,) = crosscheck.check_constant(Path(), mentions_only)
    assert "names no declaring site" in fault.detail


def test_check_constant_refuses_a_mention_on_an_ordering() -> None:
    """An ordering has two different legal values, so there is no one value to go looking for."""
    muddled = ORDERING._replace(mentions=(crosscheck.Mention("a.css", "{value}"),))
    (fault,) = crosscheck.check_constant(Path(), muddled)
    assert "no one value a mention could spell" in fault.detail


# ── orderings, where one bound must sit under another ──────────────────────────


ORDERING = crosscheck.Constant(
    label="an ordering",
    why="the lower bound must stay under the upper one",
    sites=(
        crosscheck.Site("body.rs", "MAX_EDGE_CEILING"),
        crosscheck.Site("brain.py", "MAX_IMAGE_EDGE"),
    ),
    relation=crosscheck.Relation.ORDERED,
)


def _order(root: Path, lower: str, upper: str) -> None:
    (root / "body.rs").write_text(f"const MAX_EDGE_CEILING: u32 = {lower};\n", encoding="utf-8")
    (root / "brain.py").write_text(f"MAX_IMAGE_EDGE = {upper}\n", encoding="utf-8")


@pytest.mark.parametrize(("lower", "upper"), [("4096", "8192"), ("8192", "8192")])
def test_an_ordering_holds_below_and_at_the_bound(tmp_path: Path, lower: str, upper: str) -> None:
    """The whole reason for the comparator: these two pass here and would fail as an equality."""
    _order(tmp_path, lower, upper)
    assert crosscheck.check_constant(tmp_path, ORDERING) == []


def test_an_ordering_fails_when_the_lower_bound_climbs_past_the_upper(tmp_path: Path) -> None:
    _order(tmp_path, "16384", "8192")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "not non-decreasing in registry order" in fault.detail
    assert "MAX_EDGE_CEILING = 16384" in fault.detail
    assert ORDERING.why in fault.detail


def test_the_same_sites_under_an_equality_would_be_a_fault(tmp_path: Path) -> None:
    """Proof the relation field is read rather than decorative: same tree, two verdicts."""
    _order(tmp_path, "4096", "8192")
    equal = ORDERING._replace(relation=crosscheck.Relation.EQUAL)
    (fault,) = crosscheck.check_constant(tmp_path, equal)
    assert "not identical" in fault.detail


def test_an_ordering_over_strings_is_refused(tmp_path: Path) -> None:
    """Fail closed: `<=` on text would silently compare alphabetically."""
    (tmp_path / "body.rs").write_text('const MAX_EDGE_CEILING: &str = "a";\n', encoding="utf-8")
    (tmp_path / "brain.py").write_text('MAX_IMAGE_EDGE = "b"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "an ordering compares numbers" in fault.detail


# ── mentions, where the far side spends a value it never declares ──────────────


MENTIONED = crosscheck.Constant(
    label="a spent value",
    why="the stylesheet reads back what the module publishes",
    sites=(crosscheck.Site("budget.ts", "CEILING_PROPERTY"),),
    mentions=(crosscheck.Mention("overlay.css", "var({value},"),),
)


def _spend(root: Path, declared: str, spelled: str) -> None:
    (root / "budget.ts").write_text(f'const CEILING_PROPERTY = "{declared}";\n', encoding="utf-8")
    (root / "overlay.css").write_text(f".panel {{ height: var({spelled}, 100vh); }}\n", "utf-8")


def test_a_mention_found_in_the_shape_it_names_is_tied(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", spelled="--ceiling")
    assert crosscheck.check_constant(tmp_path, MENTIONED) == []


def test_a_rename_on_the_declaring_side_leaves_the_needle_unfound(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--roof", spelled="--ceiling")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "does not spell 'var(--roof,'" in fault.detail


def test_a_rename_on_the_spending_side_leaves_it_unfound_too(tmp_path: Path) -> None:
    """Symmetry is the point: neither side can move alone, and neither is the master."""
    _spend(tmp_path, declared="--ceiling", spelled="--roof")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "does not spell 'var(--ceiling,'" in fault.detail


def _ported(template: str) -> crosscheck.Constant:
    """A port declared in one file and spent in a compose publish, under a given template."""
    return crosscheck.Constant(
        label="a port",
        why="the stack publishes what the server binds",
        sites=(crosscheck.Site("config.py", "PORT"),),
        mentions=(crosscheck.Mention("stack.yml", template),),
    )


def _publish(root: Path, declared: str, host: str, container: str) -> None:
    (root / "config.py").write_text(f"PORT = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(f'      - "127.0.0.1:{host}:{container}"\n', encoding="utf-8")


def test_a_mention_of_a_number_renders_it_as_written(tmp_path: Path) -> None:
    _publish(tmp_path, declared="50051", host="50051", container="50051")
    assert crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}")) == []


def test_a_number_a_longer_one_merely_contains_is_not_spelled(tmp_path: Path) -> None:
    """The pass this bound removed: `5005` sits inside `50051`, so containment agreed with it."""
    _publish(tmp_path, declared="5005", host="50051", container="50051")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}"))
    assert "does not spell '127.0.0.1:5005' as a token of its own" in fault.detail


def test_a_template_that_pins_only_the_host_half_leaves_the_other_free(tmp_path: Path) -> None:
    """Why the registry spells a published pair whole: the halves are two different numbers."""
    _publish(tmp_path, declared="50051", host="50051", container="50052")
    assert crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}")) == []
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "does not spell '127.0.0.1:50051:50051'" in fault.detail


@pytest.mark.parametrize(
    ("needle", "text", "found"),
    [
        ("50051", "  - 50051\n", True),
        ("50051", "  - 500511\n", False),  # a longer number, whose prefix this is
        ("50051", "  - 150051\n", False),  # the same on the leading edge
        ("var(--ceiling,", "height: var(--ceiling, 100vh);", True),  # punctuation at both edges
        ("--ease: linear", "--ease: linearity;", False),  # punctuation leading, a word trailing
        ("[data-morphing", ".view:has([data-morphing]) {", True),
    ],
)
def test_a_needle_is_bounded_at_whichever_edge_is_a_word(
    needle: str, text: str, *, found: bool
) -> None:
    """Only a word edge needs a guard; `var(--ceiling,` bounds itself with its own punctuation."""
    assert bool(crosscheck.bounded(needle).search(text)) is found


def test_a_mention_on_a_file_that_cannot_be_read_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "cannot read overlay.css" in fault.detail


def test_a_mention_template_that_spells_no_value_is_refused(tmp_path: Path) -> None:
    """A template without the placeholder would match forever without tying anything."""
    _spend(tmp_path, declared="--ceiling", spelled="--ceiling")
    blind = MENTIONED._replace(mentions=(crosscheck.Mention("overlay.css", ".panel"),))
    (fault,) = crosscheck.check_constant(tmp_path, blind)
    assert "carries no {value}" in fault.detail


def test_every_mention_is_reported_rather_than_only_the_first(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", spelled="--roof")
    both = MENTIONED._replace(
        mentions=(*MENTIONED.mentions, crosscheck.Mention("gone.css", "var({value})"))
    )
    details = [fault.detail for fault in crosscheck.check_constant(tmp_path, both)]
    assert len(details) == 2
    assert "cannot read gone.css" in details[1]


# ── counted mentions, where the occurrences are one set ────────────────────────


def _compare(root: Path, declared: str, *spelled: str) -> None:
    """A state literal declared once and compared against in a component, once per line given."""
    (root / "channels.py").write_text(f'STATE = "{declared}"\n', encoding="utf-8")
    lines = "".join(f'  aria-label={{s === "{one}" ? "x" : undefined}}\n' for one in spelled)
    (root / "Message.tsx").write_text(f"<span\n{lines}/>\n", encoding="utf-8")


def _counted(occurrences: int | None) -> crosscheck.Constant:
    return crosscheck.Constant(
        label="a compared state",
        why="both comparisons decide on the same state",
        sites=(crosscheck.Site("channels.py", "STATE"),),
        mentions=(crosscheck.Mention("Message.tsx", 's === "{value}"', occurrences),),
    )


def test_a_counted_mention_holds_when_the_whole_set_is_spelled(tmp_path: Path) -> None:
    _compare(tmp_path, "thinking", "thinking", "thinking")
    assert crosscheck.check_constant(tmp_path, _counted(2)) == []


def test_a_half_applied_rename_passes_a_presence_check_and_fails_a_counted_one(
    tmp_path: Path,
) -> None:
    """The recorded defect, in one tree: one of two comparisons updated, the other left dead."""
    _compare(tmp_path, "deliberating", "deliberating", "thinking")
    assert crosscheck.check_constant(tmp_path, _counted(None)) == []
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    spelling = "spells 's === \"deliberating\"' as a token of its own: found 1, pinned 2"
    assert spelling in fault.detail


def test_a_counted_mention_fails_on_one_occurrence_too_many(tmp_path: Path) -> None:
    """Exact rather than a floor: a set that grew is a set whose registry line is now stale."""
    _compare(tmp_path, "thinking", "thinking", "thinking", "thinking")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    assert "found 3, pinned 2" in fault.detail


def test_a_counted_mention_on_a_file_that_cannot_be_read_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "channels.py").write_text('STATE = "thinking"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    assert "cannot read Message.tsx" in fault.detail


@pytest.mark.parametrize("occurrences", [0, -1])
def test_a_count_below_one_is_refused(tmp_path: Path, occurrences: int) -> None:
    """Zero would ask a mention to prove the value ABSENT, which is the opposite of a coupling."""
    _compare(tmp_path, "thinking", "thinking")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(occurrences))
    assert f"pins {occurrences} occurrences, which ties nothing" in fault.detail


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


def test_every_registered_constant_spans_more_than_one_language() -> None:
    """An entry whose places were all one language would prove nothing about a seam.

    This used to demand more than one top-level TREE, which was right while every registered
    coupling crossed the body/brain seam. Mentions moved the line: the overlay's TypeScript and
    the stylesheet that spends what it publishes live in one tree and are two languages, and
    the rename that breaks them is exactly what this scan is for. Suffix is the honest test.
    """
    for constant in crosscheck.CONSTANTS:
        places = [site.path for site in constant.sites]
        places.extend(mention.path for mention in constant.mentions)
        assert len({Path(place).suffix for place in places}) > 1, constant.label


def test_every_registered_mention_carries_the_placeholder() -> None:
    """A template without it would find itself in any file and tie nothing."""
    for constant in crosscheck.CONSTANTS:
        for mention in constant.mentions:
            assert crosscheck.PLACEHOLDER in mention.template, constant.label


def test_the_registry_exercises_both_relations() -> None:
    """A comparator no entry uses is a widened gate that cannot fail, which is the same defect."""
    assert {constant.relation for constant in crosscheck.CONSTANTS} == set(crosscheck.Relation)


def test_the_registry_holds_couplings_of_both_kinds() -> None:
    """Same argument for the mention form: an unexercised site kind proves nothing."""
    assert any(constant.mentions for constant in crosscheck.CONSTANTS)
    assert any(len(constant.sites) > 1 for constant in crosscheck.CONSTANTS)


def test_the_registry_pins_at_least_one_occurrence_count() -> None:
    """A field no entry sets is a dead wire, and this repo declines those."""
    counted = [
        mention.occurrences
        for constant in crosscheck.CONSTANTS
        for mention in constant.mentions
        if mention.occurrences is not None
    ]
    assert counted
    assert all(count >= crosscheck.MIN_OCCURRENCES for count in counted)


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
