import re
from collections import Counter
from collections.abc import Callable
from importlib import import_module
from pathlib import Path

import pytest

import couplings
import crosscheck
import needles
import registry
import values

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


# ── finding a declaration in each language ─────────────────────────────────────
#
# The reduction itself (which right-hand sides become which values, and which are refused) is
# `values.py`'s half and is tested in `test_values.py`; what is tested here is finding the
# declaration to reduce, and what the scan makes of the values once it has them.


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
    assert "an ordering compares integers" in fault.detail


def test_an_ordering_over_decimals_is_refused_too(tmp_path: Path) -> None:
    """A decimal is digits here, and `<=` over digits would file `10.0` under `9.0`."""
    _order(tmp_path, "4.0", "8.0")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "an ordering compares integers" in fault.detail


def _two_python_bounds(root: Path, lower: str, upper: str) -> crosscheck.Constant:
    """An ordering over two Python files, for the values no `u32` would honestly hold."""
    (root / "one.py").write_text(f"LOWER = {lower}\n", encoding="utf-8")
    (root / "other.py").write_text(f"UPPER = {upper}\n", encoding="utf-8")
    return ORDERING._replace(
        sites=(crosscheck.Site("one.py", "LOWER"), crosscheck.Site("other.py", "UPPER"))
    )


def test_an_ordering_over_booleans_is_refused_too(tmp_path: Path) -> None:
    """An answer with two values has no order, and Python's `False == 0` must not supply one."""
    ordering = _two_python_bounds(tmp_path, "False", "True")
    (fault,) = crosscheck.check_constant(tmp_path, ordering)
    assert "an ordering compares integers" in fault.detail


@pytest.mark.parametrize(("lower", "upper"), [("-1", "0"), ("-2", "-1")])
def test_an_ordering_sorts_a_signed_bound_as_the_number_it_is(
    tmp_path: Path, lower: str, upper: str
) -> None:
    """The other half of the sign: a signed integer is a number here and orders like one."""
    ordering = _two_python_bounds(tmp_path, lower, upper)
    assert crosscheck.check_constant(tmp_path, ordering) == []


def test_an_ordering_catches_a_signed_bound_that_climbed(tmp_path: Path) -> None:
    """And it is a real comparison rather than a text one, which would file `-1` under `-2`."""
    ordering = _two_python_bounds(tmp_path, "-1", "-2")
    (fault,) = crosscheck.check_constant(tmp_path, ordering)
    assert "not non-decreasing in registry order" in fault.detail


# ── memberships, where one side's value must be one of the other's ─────────────


MEMBERSHIP = crosscheck.Constant(
    label="a membership",
    why="the one encoding produced must be one the allow-list carries",
    sites=(
        crosscheck.Site("body.rs", "CAPTURE_MIME"),
        crosscheck.Site("brain.py", "ALLOWED_MIME_TYPES"),
    ),
    relation=crosscheck.Relation.MEMBER,
)


def _allow(root: Path, produced: str, *allowed: str) -> None:
    """The membership's real shape: a Rust `&str` const against a Python `frozenset` of them."""
    declaration = f'pub const CAPTURE_MIME: &str = "{produced}";\n'
    (root / "body.rs").write_text(declaration, encoding="utf-8")
    members = ", ".join(f'"{one}"' for one in allowed)
    (root / "brain.py").write_text(f"ALLOWED_MIME_TYPES = frozenset({{{members}}})\n", "utf-8")


def test_a_membership_holds_wherever_in_the_collection_the_value_sits(tmp_path: Path) -> None:
    """The whole reason for the comparator: neither equal nor ordered, and still a real tie."""
    _allow(tmp_path, "image/png", "image/png", "image/jpeg", "image/webp")
    assert crosscheck.check_constant(tmp_path, MEMBERSHIP) == []


def test_a_membership_fails_when_the_collection_drops_the_value(tmp_path: Path) -> None:
    """The drift this closes: the allow-list narrows and the body keeps producing what it lost."""
    _allow(tmp_path, "image/png", "image/jpeg", "image/webp")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "not members of the collection the last site declares" in fault.detail
    assert "body.rs: CAPTURE_MIME = 'image/png'" in fault.detail
    assert MEMBERSHIP.why in fault.detail


def test_a_membership_fails_when_the_value_leaves_the_collection(tmp_path: Path) -> None:
    """The same drift from the other side, since neither side of a coupling is the master."""
    _allow(tmp_path, "image/gif", "image/png", "image/jpeg")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "body.rs: CAPTURE_MIME = 'image/gif'" in fault.detail


def test_a_membership_needs_a_collection_at_the_last_site(tmp_path: Path) -> None:
    """Fail closed: `in` over two strings would answer about substrings instead."""
    _allow(tmp_path, "image/png")
    (tmp_path / "brain.py").write_text('ALLOWED_MIME_TYPES = "image/png"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "a membership needs a collection at the last site" in fault.detail


def test_the_same_sites_under_an_equality_would_be_a_fault_too(tmp_path: Path) -> None:
    """Proof this relation is read rather than decorative: same tree, two verdicts."""
    _allow(tmp_path, "image/png", "image/png", "image/jpeg")
    equal = MEMBERSHIP._replace(relation=crosscheck.Relation.EQUAL)
    (fault,) = crosscheck.check_constant(tmp_path, equal)
    assert "not identical" in fault.detail


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
    assert "carrying it only inside a longer token" in fault.detail


def test_a_template_that_pins_only_the_host_half_leaves_the_other_free(tmp_path: Path) -> None:
    """Why the registry spells a published pair whole: the halves are two different numbers."""
    _publish(tmp_path, declared="50051", host="50051", container="50052")
    assert crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}")) == []
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "does not spell '127.0.0.1:50051:50051'" in fault.detail


# ── what an unfound needle says about whose literal stopped matching ───────────
#
# A needle is a value plus shape and the shape is other people's text, so an unfound one used to
# name the entry it belongs to over a literal that entry does not own. `needles.py` reports
# whether the file still spells this constant's own value, and how much of the needle it carries.


def _publish_on(root: Path, interface: str) -> None:
    """The publish with its host-side interface moved and both port halves left alone."""
    (root / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (root / "stack.yml").write_text(f'      - "{interface}:50051:50051"\n', encoding="utf-8")


def test_a_moved_neighbour_is_reported_as_shape_and_not_as_this_value(tmp_path: Path) -> None:
    """The misattribution measured on the real tree: the publish's interface is not the port."""
    _publish_on(tmp_path, "127.0.0.2")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "carrying no more of it than '127.0.0.', which stops on line 1" in fault.detail
    assert "the file does still spell '50051' as a token of its own" in fault.detail
    assert "the constant to change may not be the one named here" in fault.detail


def test_a_moved_value_is_reported_as_absent_and_blames_no_neighbour(tmp_path: Path) -> None:
    """The other direction, which must NOT blame shape: the port itself is what moved."""
    _publish(tmp_path, declared="50052", host="50051", container="50051")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}"))
    assert "carrying no more of it than '127.0.0.1:5005'" in fault.detail
    assert "the file does not spell '50052' as a token of its own either" in fault.detail


def test_a_value_left_only_inside_a_decimal_is_not_read_as_still_being_spelled(
    tmp_path: Path,
) -> None:
    """The misattribution the decimal guard removes, in the reading that would have made it.

    The swap runbook states the `10 s` grace on the same line as a `10.09 s` latency. Take the
    grace out and the needle is unfound either way; what changes is what the fault then says.
    Reading the whole part of that latency as the value still being spelled would send the reader
    off to hunt a neighbour's literal that never moved, which is what this reading prevents.
    """
    (tmp_path / "config.py").write_text("DEFAULT_STOP_GRACE_S = 10\n", encoding="utf-8")
    (tmp_path / "swap.md").write_text("answered in **10.09 s**, so the\n", encoding="utf-8")
    graced = crosscheck.Constant(
        label="the grace a child gets before it is killed",
        why="an eviction pays this whole grace when the child has a request in flight",
        sites=(crosscheck.Site("config.py", "DEFAULT_STOP_GRACE_S"),),
        mentions=(crosscheck.Mention("swap.md", "{value} s"),),
    )
    (fault,) = crosscheck.check_constant(tmp_path, graced)
    assert "does not spell '10 s' as a token of its own" in fault.detail
    assert "carrying no more of it than '10', which stops on line 1" in fault.detail
    assert "the file does not spell '10' as a token of its own either" in fault.detail


def test_a_file_carrying_no_part_of_the_needle_has_no_run_to_report(tmp_path: Path) -> None:
    """A needle whose opening character is absent: there is nothing of it to quote back."""
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (tmp_path / "overlay.css").write_text(".panel { height: 100px; }\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "carrying no part of it" in fault.detail
    assert "does not spell '--ceiling' as a token of its own either" in fault.detail


# ── and where it read the value it says is still there ─────────────────────────
#
# A maybe nobody can check is a grep, which is the work this reading exists to save. So a yes
# names the line, reads it back, and says how many lines spell the value: `needles.where`. The
# run says the same three things about itself (`needles.stops`), because the evidence a reader
# weighs is the distance between the two: a value on the line the run stops on is the strong form
# of "what moved is shape", and one two lines below it, as here, is the weak form.


_GRACED = crosscheck.Constant(
    label="the grace a child gets before it is killed",
    why="an eviction pays this whole grace when the child has a request in flight",
    sites=(crosscheck.Site("config.py", "DEFAULT_STOP_GRACE_S"),),
    mentions=(crosscheck.Mention("swap.md", "the full grace ({value} s)"),),
)


def _graced(root: Path, swap: str) -> None:
    """The grace retuned past what the runbook states, over a runbook of the caller's writing."""
    (root / "config.py").write_text("DEFAULT_STOP_GRACE_S = 11\n", encoding="utf-8")
    (root / "swap.md").write_text(swap, encoding="utf-8")


def test_a_yes_reads_back_the_line_it_read_the_value_on(tmp_path: Path) -> None:
    """The homonym that opened this, in miniature: one `11`, and it is about VRAM.

    The reading is not lying and cannot be made to stop saying maybe, a document being free to
    spell two digits under two meanings. What it can do is hand the reader the sentence, which is
    what settles this one on sight instead of on a grep.
    """
    _graced(
        tmp_path,
        "the full grace (10 s) is paid when a request is in flight\n"
        "\n"
        "the cortex still holds ~11 GB of it while it dies\n",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "which stops on line 1" in fault.detail
    assert "the file does still spell '11' as a token of its own, once on line 3" in fault.detail
    assert "which reads 'the cortex still holds ~11 GB of it while it dies'" in fault.detail


def test_a_last_line_with_no_newline_is_still_read_back_whole(tmp_path: Path) -> None:
    """The line the file ends on has no closing newline to find, and is a line all the same."""
    _graced(tmp_path, "the full grace (10 s) is paid\n\nthe cortex holds ~11 GB")
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "once on line 3, which reads 'the cortex holds ~11 GB'" in fault.detail


def test_the_run_is_measured_where_it_stops_and_not_where_it_starts(tmp_path: Path) -> None:
    """A value on either side of a long run, which is what tells the two ends of it apart.

    The run is what the file stopped agreeing at, so the spelling that matters is the one nearest
    its stop. Reading from its start instead would put the whole length of the run into every
    distance and name the line above, which here is a paragraph the divergence has nothing to do
    with.
    """
    _graced(
        tmp_path,
        "11 GB of it is still held\nand the full grace (10 s) is paid\nwhich leaves 11 free\n",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "carrying no more of it than 'the full grace (1', which stops on line 2" in fault.detail
    assert "in 2 places, the nearest to that run on line 3" in fault.detail
    assert "which reads 'which leaves 11 free'" in fault.detail


def test_a_value_in_several_places_is_counted_and_read_nearest_the_run(tmp_path: Path) -> None:
    """Which of several: the one nearest where the file stopped carrying the needle.

    The two readings a fault carries are about one divergence, so they name one place. Here the
    publish's own interface is what moved, the run stops inside it, and the port is spelled both
    on that line and in a comment seven lines above that has nothing to do with it.
    """
    (tmp_path / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(
        "# the brain answered on 50051 before the move\n\n\n\n\n\n\n"
        '      - "127.0.0.2:50051:50051"\n',
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "carrying no more of it than '127.0.0.', which stops on line 8" in fault.detail
    assert "in 3 places, the nearest to that run on line 8" in fault.detail
    assert "which reads '- \"127.0.0.2:50051:50051\"'" in fault.detail


def test_a_run_carried_in_several_places_names_the_stop_nearest_the_spelling(
    tmp_path: Path,
) -> None:
    """The other end of the same distance, where the run is what the file carries twice.

    A run is a prefix, so another publish satisfies it on a line the reader does not mean: here
    the brain's host port moved and the redis publish seven lines above goes on carrying the
    interface the needle opens with. The two readings name one place, so the stop the message
    gives is the one the quoted spelling was measured against and not the first in the file.
    """
    (tmp_path / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(
        '      - "127.0.0.1:6379:6379"\n\n\n\n\n\n\n      - "127.0.0.1:9090:50051"\n',
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "which stops in 2 places, the nearest to that spelling on line 8" in fault.detail
    assert "still spell '50051' as a token of its own, once on line 8" in fault.detail


def test_a_value_in_several_places_with_no_run_at_all_is_read_at_the_first(tmp_path: Path) -> None:
    """No run means no place to be nearest to, so the first spelling is the one named."""
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (tmp_path / "overlay.css").write_text(
        ".panel { height: --ceiling; }\n.rail { width: --ceiling; }\n", encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "carrying no part of it" in fault.detail
    assert "in 2 places, the first on line 1" in fault.detail
    assert "which reads '.panel { height: --ceiling; }'" in fault.detail


def _row(before: int, after: int) -> tuple[str, int, int]:
    """A table row of a chosen width with `2048` at a chosen depth into it, and where that sits."""
    line = f"| {'w' * before} | 2048 | {'x' * after} |"
    return line, line.index("2048"), line.index("2048") + len("2048")


@pytest.mark.parametrize(
    ("before", "after", "opens", "closes"),
    [
        (2, 2, False, False),  # a line inside the width is quoted whole
        (200, 200, True, True),  # a runbook row, windowed at both ends
        (2, 400, False, True),  # the value near the line's start: nothing to trim in front
        (400, 2, True, False),  # and near its end: nothing to trim after
    ],
)
def test_a_quote_is_windowed_only_where_the_line_runs_past_it(
    before: int, after: int, *, opens: bool, closes: bool
) -> None:
    """A fault is one sentence, so the widest line this gate reads is quoted around the match."""
    line, start, end = _row(before, after)
    read = needles.quote(line, start, end)
    assert "2048" in read
    assert len(read) <= needles.QUOTED_WIDTH + 2 * len(needles.TRIMMED)
    assert read.startswith(needles.TRIMMED) is opens
    assert read.endswith(needles.TRIMMED) is closes


def test_a_needle_that_renders_only_a_name_is_shape_all_through(tmp_path: Path) -> None:
    """A name-only needle spells the value nowhere, so there is no value to report on."""
    _restate(tmp_path, "--roll", "--ease", "--ease")
    spent = RESTATED._replace(
        mentions=(RESTATED.mentions[0], RESTATED.mentions[1]._replace(occurrences=None)),
    )
    (fault,) = crosscheck.check_constant(tmp_path, spent)
    assert "does not spell 'var(--roll)' as a token of its own" in fault.detail
    assert "carrying no more of it than 'var(--'" in fault.detail
    assert "which stops in 2 places, the first on line 2" in fault.detail
    assert "this needle renders no value, so the whole of it is shape" in fault.detail


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


@pytest.mark.parametrize(
    ("needle", "text", "found"),
    [
        ("2048", "the shipped edge is 2048.", True),  # a full stop ends a sentence, not a number
        ("2048", "resampled to 2048.5 px", False),  # a digit past the point continues the number
        ("2048", "measured at 0.2048 of the edge", False),  # the same rule read from the far end
        ("2048", "the ceiling. 2048 is the edge", True),  # a full stop before it, and a space
        ("6291456", "outside `1..6291456`", True),  # a range's second point is not a decimal one
        ("10", "the full grace (10 s) was paid", True),  # the swap runbook's real reading
        ("10", "answered in **10.09 s**", False),  # the latency it was mistaken for
        ("10", "stop answered in **0.10 s**", False),  # and the one three lines below it
        ("insecure_channel(", "grpc.insecure_channel(", True),  # a letter past a point is a name
        ("auto", "tiers.2.auto is the shipped mode", True),  # a dotted key indexed by a number
        ("tiers", "tiers.2 is the deep one", True),  # the same key read from its other end
        ("--ease: linear", "0.--ease: linear;", True),  # punctuation edges take no guard at all
    ],
)
def test_a_point_between_two_digits_is_inside_a_number_and_not_a_full_stop(
    needle: str, text: str, *, found: bool
) -> None:
    """The edge a word guard cannot see: a point is a word character at neither of its ends.

    So the guard a digit edge takes reads the FAR side of the point, which is the one reading that
    tells a sentence ending on a number from a number that goes on past its point. An edge that is
    a word but not a digit takes no such guard: `grpc.` is attribute access.
    """
    assert bool(crosscheck.bounded(needle).search(text)) is found


def test_a_mention_on_a_file_that_cannot_be_read_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "cannot read overlay.css" in fault.detail


def test_a_mention_template_that_renders_nothing_is_refused(tmp_path: Path) -> None:
    """A template with neither placeholder would match forever without tying anything."""
    _spend(tmp_path, declared="--ceiling", spelled="--ceiling")
    blind = MENTIONED._replace(mentions=(crosscheck.Mention("overlay.css", ".panel"),))
    (fault,) = crosscheck.check_constant(tmp_path, blind)
    assert "renders neither {value} nor {name}" in fault.detail


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


# ── named mentions, where the template renders the name and not the value ──────


RESTATED = crosscheck.Constant(
    label="a restated duration",
    why="the sheet restates the module's number, and the rules that follow it spend the name",
    sites=(crosscheck.Site("morph.ts", "ROLL_MS"),),
    mentions=(
        crosscheck.Mention("overlay.css", "{name}: {value}ms;", name="--roll"),
        crosscheck.Mention("overlay.css", "var({name})", name="--roll", occurrences=2),
    ),
)


def _restate(root: Path, declared: str, *spent: str) -> None:
    """A duration owned in TypeScript, restated on `:root` as a property, spent by two rules."""
    (root / "morph.ts").write_text("export const ROLL_MS = 300;\n", encoding="utf-8")
    rules = "".join(f".s{i} {{ transition: var({one}); }}\n" for i, one in enumerate(spent))
    (root / "overlay.css").write_text(f":root {{ {declared}: 300ms; }}\n{rules}", "utf-8")


def test_a_named_mention_holds_when_the_sheet_declares_and_spends_one_property(
    tmp_path: Path,
) -> None:
    _restate(tmp_path, "--roll", "--roll", "--roll")
    assert crosscheck.check_constant(tmp_path, RESTATED) == []


def test_a_mistyped_spend_fails_where_a_rendered_value_never_reached_it(tmp_path: Path) -> None:
    """The gap this form closes: the value is spelled on `:root` and no spend carries it."""
    _restate(tmp_path, "--roll", "--roll", "--rol")
    value_only = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "--roll: {value}ms;"),)
    )
    assert crosscheck.check_constant(tmp_path, value_only) == []
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert "spells 'var(--roll)' as a token of its own: found 1, pinned 2" in fault.detail


def test_a_spend_that_pays_a_neighbouring_property_is_a_spend_short(tmp_path: Path) -> None:
    """Paying the wrong property costs the same as paying none, and both properties exist."""
    _restate(tmp_path, "--roll", "--roll", "--ease")
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert "found 1, pinned 2" in fault.detail


def test_renaming_the_declared_property_leaves_the_declaration_unfound(tmp_path: Path) -> None:
    """The other half of the pair: the spends still agree with each other and pay nothing."""
    _restate(tmp_path, "--cadence", "--roll", "--roll")
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert "does not spell '--roll: 300ms;' as a token of its own" in fault.detail


def test_a_template_rendering_a_name_the_mention_does_not_carry_is_refused(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--roll", "--roll")
    nameless = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "{name}: {value}ms;"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, nameless)
    assert "renders a name the mention does not carry" in fault.detail


def test_a_name_the_template_renders_nowhere_is_refused(tmp_path: Path) -> None:
    """Dead data in a registry reads as a tie and is not one, so it is a fault and not a shrug."""
    _restate(tmp_path, "--roll", "--roll", "--roll")
    unspent = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "--roll: {value}ms;", name="--roll"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, unspent)
    assert "renders it nowhere" in fault.detail


def test_a_spent_name_no_mention_pays_the_value_under_is_refused(tmp_path: Path) -> None:
    """Held name, dropped value: the spend would be tied to a declaration nothing reads."""
    unpaid = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "var({name})", name="--roll"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, unpaid)
    assert "no mention renders the value under that name" in fault.detail


# ── decimals, where the digits ARE the value ───────────────────────────────────


DEADLINE = crosscheck.Constant(
    label="a shipped deadline",
    why="the stack substitutes the default the adapter declares",
    sites=(crosscheck.Site("gateway.py", "DEFAULT_CALL_TIMEOUT_S"),),
    mentions=(crosscheck.Mention("stack.yml", "${CORTEX_BODY_CALL_TIMEOUT_S:-{value}}"),),
)


def _deadline(root: Path, declared: str, substituted: str) -> None:
    """A deadline owned by an adapter and spelled again as a compose substitution default."""
    (root / "gateway.py").write_text(f"DEFAULT_CALL_TIMEOUT_S = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      CORTEX_BODY_CALL_TIMEOUT_S: "${{CORTEX_BODY_CALL_TIMEOUT_S:-{substituted}}}"\n',
        encoding="utf-8",
    )


def test_a_decimal_renders_into_the_shape_a_stack_substitutes(tmp_path: Path) -> None:
    _deadline(tmp_path, declared="5.0", substituted="5.0")
    assert crosscheck.check_constant(tmp_path, DEADLINE) == []


def test_retuning_the_adapter_alone_leaves_every_deployment_on_the_old_number(
    tmp_path: Path,
) -> None:
    """The drift this entry is registered for, in one tree."""
    _deadline(tmp_path, declared="7.5", substituted="5.0")
    (fault,) = crosscheck.check_constant(tmp_path, DEADLINE)
    assert "does not spell '${CORTEX_BODY_CALL_TIMEOUT_S:-7.5}'" in fault.detail


def test_the_same_number_without_its_point_is_a_different_spelling(tmp_path: Path) -> None:
    """Why the reduction stays textual: the needle is built out of the digits, not the number."""
    _deadline(tmp_path, declared="5", substituted="5.0")
    (fault,) = crosscheck.check_constant(tmp_path, DEADLINE)
    assert "does not spell '${CORTEX_BODY_CALL_TIMEOUT_S:-5}'" in fault.detail


def _both_declare(root: Path, rust: str, python: str) -> None:
    (root / "body.rs").write_text(f"const LEASE_S: f64 = {rust};\n", encoding="utf-8")
    (root / "brain.py").write_text(f"LEASE_S = {python}\n", encoding="utf-8")


DECIMAL_PAIR = crosscheck.Constant(
    label="a shared decimal",
    why="both sides lease for the same length of time",
    sites=(crosscheck.Site("body.rs", "LEASE_S"), crosscheck.Site("brain.py", "LEASE_S")),
)


def test_two_decimal_sites_tie_across_languages(tmp_path: Path) -> None:
    _both_declare(tmp_path, rust="2.5", python="2.5")
    assert crosscheck.check_constant(tmp_path, DECIMAL_PAIR) == []


def test_two_decimal_sites_that_drift_are_reported_with_both_digits(tmp_path: Path) -> None:
    """A decimal prints as itself in a fault, so the reader sees the two spellings."""
    _both_declare(tmp_path, rust="2.5", python="2.50")
    (fault,) = crosscheck.check_constant(tmp_path, DECIMAL_PAIR)
    assert "not identical" in fault.detail
    assert "body.rs: LEASE_S = 2.5," in fault.detail
    assert "brain.py: LEASE_S = 2.50" in fault.detail


# ── two spellings of one number ────────────────────────────────────────────────


BUDGET = crosscheck.Constant(
    label="a memory budget",
    why="the scheduler admits against the number the cgroup enforces",
    sites=(crosscheck.Site("config.py", "DEFAULT_MEM_BUDGET_GB"),),
    mentions=(
        crosscheck.Mention("stack.yml", '"${BUDGET_GB:-{value}}"'),
        crosscheck.Mention(
            "stack.yml",
            '"${BUDGET_GB:-{value}}g"',
            occurrences=2,
            spelling=couplings.Spelling.WHOLE,
        ),
    ),
)


def _budget(root: Path, declared: str, passed: str, limit: str) -> None:
    """The real shape: one budget passed to a process and enforced as a docker size beside it."""
    (root / "config.py").write_text(f"DEFAULT_MEM_BUDGET_GB = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      BUDGET_GB: "${{BUDGET_GB:-{passed}}}"\n'
        f'    mem_limit: "${{BUDGET_GB:-{limit}}}g"\n'
        f'    memswap_limit: "${{BUDGET_GB:-{limit}}}g"\n',
        encoding="utf-8",
    )


def test_one_number_ties_the_far_side_that_cannot_spell_it_as_written(tmp_path: Path) -> None:
    """`8.0g` is not a size docker accepts, so the limits spell the same number without a point."""
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    assert crosscheck.check_constant(tmp_path, BUDGET) == []


def test_retuning_the_budget_alone_reddens_both_spellings(tmp_path: Path) -> None:
    """The drift this is registered for: a container capped under what the scheduler admits."""
    _budget(tmp_path, declared="12.0", passed="8.0", limit="8")
    written, whole = crosscheck.check_constant(tmp_path, BUDGET)
    assert "does not spell '\"${BUDGET_GB:-12.0}\"'" in written.detail
    assert "'\"${BUDGET_GB:-12}g\"' as a token of its own: found 0, pinned 2" in whole.detail


def test_one_of_the_two_limits_moving_alone_is_a_count_short(tmp_path: Path) -> None:
    """Memswap equal to memory is what disables swap, so the pair moves together or not at all."""
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    stack = tmp_path / "stack.yml"
    stack.write_text(
        stack.read_text(encoding="utf-8").replace(':-8}g"\n    memswap', ':-9}g"\n    memswap'),
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "found 1, pinned 2" in fault.detail


def test_a_site_that_drops_its_point_is_still_caught(tmp_path: Path) -> None:
    """What the whole spelling must not undo: `8` and `8.0` render alike whole and differ written.

    The re-spelled mention is blind here by construction, both spellings of one whole number
    being the same text, and that is why the entry carries a written mention beside it.
    """
    _budget(tmp_path, declared="8", passed="8.0", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "does not spell '\"${BUDGET_GB:-8}\"'" in fault.detail


def test_a_budget_the_far_side_cannot_spell_at_all_is_reported(tmp_path: Path) -> None:
    """A fraction docker's suffix cannot carry is a fault, never a quietly truncated limit."""
    _budget(tmp_path, declared="8.5", passed="8.5", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "8.5 cannot be spelled whole" in fault.detail


def test_an_entry_that_re_spells_everywhere_is_refused(tmp_path: Path) -> None:
    """A registry entry with no written reading holds nothing against a site changing spelling."""
    blind = BUDGET._replace(mentions=BUDGET.mentions[1:])
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, blind)
    assert "nothing holds the spelling the site writes" in fault.detail


# ── two words for one answer, and the sentinel that carries a sign ─────────────


HATCH = crosscheck.Constant(
    label="an escape hatch's shipped answer",
    why="a hatch that ships open is not a hatch",
    sites=(crosscheck.Site("config.py", "DEFAULT_TLS_INSECURE"),),
    mentions=(
        crosscheck.Mention(
            "stack.yml",
            "${TLS_INSECURE:-{value}}",
            spelling=couplings.Spelling.LOWERED,
        ),
    ),
)


def _hatch(root: Path, declared: str, substituted: str) -> None:
    """A boolean a settings module declares and a compose default spells in YAML's casing."""
    (root / "config.py").write_text(f"DEFAULT_TLS_INSECURE = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      TLS_INSECURE: "${{TLS_INSECURE:-{substituted}}}"\n', encoding="utf-8"
    )


def test_a_boolean_reaches_the_far_side_that_writes_it_in_lower_case(tmp_path: Path) -> None:
    """Neither casing can be rendered from the other's text, which is what the spelling is for."""
    _hatch(tmp_path, declared="False", substituted="false")
    assert crosscheck.check_constant(tmp_path, HATCH) == []


def test_a_hatch_the_stack_opens_alone_is_reported(tmp_path: Path) -> None:
    """The drift this form was added for: the guarantee is gone and every read path still works."""
    _hatch(tmp_path, declared="False", substituted="true")
    (fault,) = crosscheck.check_constant(tmp_path, HATCH)
    assert "does not spell '${TLS_INSECURE:-false}'" in fault.detail


def test_a_hatch_the_field_opens_alone_is_reported_too(tmp_path: Path) -> None:
    """And the other direction, which is why a lowered spelling needs nothing beside it."""
    _hatch(tmp_path, declared="True", substituted="false")
    (fault,) = crosscheck.check_constant(tmp_path, HATCH)
    assert "does not spell '${TLS_INSECURE:-true}'" in fault.detail


def test_a_boolean_a_far_side_writes_as_the_site_does_needs_no_spelling(tmp_path: Path) -> None:
    """The default spelling still reaches a far side that writes Python's own word."""
    written = HATCH._replace(
        mentions=(crosscheck.Mention("stack.yml", "${TLS_INSECURE:-{value}}"),)
    )
    _hatch(tmp_path, declared="False", substituted="False")
    assert crosscheck.check_constant(tmp_path, written) == []


SENTINEL = crosscheck.Constant(
    label="a sentinel that is a number",
    why="the stack substitutes the word the engine reads as unbounded",
    sites=(crosscheck.Site("config.py", "_UNRESTRICTED"),),
    mentions=(crosscheck.Mention("stack.yml", "${BUDGET:-{value}}"),),
)


def _sentinel(root: Path, declared: str, substituted: str) -> None:
    """A module-private sentinel and the compose default that restates it, sign and all."""
    (root / "config.py").write_text(f"_UNRESTRICTED = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      BUDGET: "${{BUDGET:-{substituted}}}"\n', encoding="utf-8"
    )


def test_a_signed_default_renders_into_the_shape_a_stack_substitutes(tmp_path: Path) -> None:
    """A leading minus survives the round trip, needle and all, under a name a module hides."""
    _sentinel(tmp_path, declared="-1", substituted="-1")
    assert crosscheck.check_constant(tmp_path, SENTINEL) == []


def test_a_sentinel_the_stack_bounds_alone_is_reported(tmp_path: Path) -> None:
    """The drift: a tier the config says is unbounded and every deployment starts bounded."""
    _sentinel(tmp_path, declared="-1", substituted="512")
    (fault,) = crosscheck.check_constant(tmp_path, SENTINEL)
    assert "does not spell '${BUDGET:--1}'" in fault.detail


def test_a_sentinel_renamed_past_its_underscore_is_a_fault_and_not_a_skip(tmp_path: Path) -> None:
    """What pays for reading a private name: the rename is reported rather than silently untied."""
    _sentinel(tmp_path, declared="-1", substituted="-1")
    (tmp_path / "config.py").write_text("_UNBOUNDED = -1\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, SENTINEL)
    assert "config.py declares no _UNRESTRICTED" in fault.detail


def test_check_walks_the_whole_registry(tmp_path: Path) -> None:
    second = BYTE_CEILING._replace(label="another ceiling")
    faults = crosscheck.check(tmp_path, (BYTE_CEILING, second))
    labels = ["a ceiling", "a ceiling", "another ceiling", "another ceiling"]
    assert [fault.label for fault in faults] == labels


# ── the registry, read against the real trees ──────────────────────────────────


def test_the_repo_itself_is_tied() -> None:
    """The gate's own assertion, run as a test so `check-scripts` catches drift too."""
    assert crosscheck.check(REPO_ROOT) == []


# ── one entry, against a tree doctored the way the defect it holds would arrive ─
#
# The whole-repo assertion above says every entry holds today; it cannot say that any one of them
# would notice the edit it was written for, because the tree is green and there is nothing to
# notice. So the reasoning-off budget is read out of the registry and applied to a COPY of the
# real files with one side retuned, which is the fault it was filed for arriving as a diff.

REASONING_OFF = "the subagent tier's reasoning-off budget"
FLAG_GATE = "scripts/flagcheck.py"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"

# The count as each side spells it: the sidecar declares it, and the flag gate requires it of
# every subagent server the compose stack starts.
DECLARED = '_NO_REASONING_BUDGET = "0"'
REQUIRED = 'Flag("--reasoning-budget", "0")'

# The other entries read out of the registry and applied to a doctored copy, and the reason they
# are the second: two of the three have a declaring side that gates nothing at all, so nothing but
# this scan runs on the day the sink moves. The reader spells both words and the sink writes both.
TRAIL_LOGGER = "the logger one recall-trail line is written through"
TRAIL_MESSAGE = "the message one recall-trail line is found by"
TRAIL_FIELD = "the field a recall-trail line names the candidates it dropped under"
TRAIL_READER = "scripts/trailwidth.py"
RECALL_SINK = "brain/packages/memory/src/cortex_memory/audit.py"
MEMORY_MODULE = "docs/modules/brain-memory.md"

SINK_LOGGER = '_LOGGER_NAME = "cortex.memory.recall"'
SINK_MESSAGE = '_logger.info("memory.recall"'
SINK_FIELD = '"dropped": ['

# The trail one part over, whose message is the entry this pair of names was added for. It is
# doctored the same way and for a sharper reason: the sample gate, which would otherwise hold a
# message, cannot read this sink's fields at all, so nothing but this scan is watching the word.
AUDIT_LOGGER = "the logger one tool-audit line is written through"
AUDIT_MESSAGE = "the message one tool-audit line is found by"
AUDIT_SINK = "brain/packages/tools/src/cortex_tools/audit.py"
LEVEL_SUITE = "brain/packages/orchestrator/tests/test_config_logging.py"

SINK_WORD = '_MESSAGE = "tool.invocation"'
ASSERTED_LINE = "INFO:cortex.tools.audit:tool.invocation tool=read"


def registered(label: str) -> couplings.Constant:
    """The one registered entry a fault would print ``label`` for."""
    found = [constant for constant in crosscheck.CONSTANTS if constant.label == label]
    assert len(found) == 1, f"the registry holds no single entry labelled {label!r}"
    return found[0]


def copied(root: Path, constant: couplings.Constant, edits: dict[str, tuple[str, str]]) -> None:
    """Copy every place ``constant`` names under ``root``, applying one edit per named file.

    The copy is what makes a mutation of the real tree a test rather than a hand run: the entry
    keeps its own paths, so a place that moves house leaves this failing instead of quietly
    checking a file nobody reads any more.
    """
    places = [site.path for site in constant.sites]
    places.extend(mention.path for mention in constant.mentions)
    for place in places:
        text = (REPO_ROOT / place).read_text(encoding="utf-8")
        if place in edits:
            was, now = edits[place]
            assert was in text, f"{place} no longer spells {was!r}, so this mutation edits nothing"
            text = text.replace(was, now, 1)
        target = root / place
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def test_the_reasoning_off_budget_holds_over_the_files_it_names(tmp_path: Path) -> None:
    """The copy with nothing edited is green, so every red below is the edit and not the copy."""
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {})
    assert crosscheck.check_constant(tmp_path, constant) == []


def test_a_gate_requiring_a_budget_the_hosted_tier_does_not_ship_is_a_fault(tmp_path: Path) -> None:
    """The compose servers and the sidecar's own tier are two halves of one tier, so a rule that
    let them disagree about what no thinking costs would slow exactly one placement."""
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {FLAG_GATE: (REQUIRED, REQUIRED.replace('"0"', '"128"'))})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [REASONING_OFF]
    assert FLAG_GATE in faults[0].detail


def test_the_hosted_tier_retuned_on_its_own_is_the_same_fault_from_the_other_side(
    tmp_path: Path,
) -> None:
    """The declaring side moving is what a needle is for: every far side goes on saying the zero
    the sidecar has stopped shipping, so all three rendered needles stop being found at once."""
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {MODELHOST_CONFIG: (DECLARED, DECLARED.replace('"0"', '"128"'))})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {REASONING_OFF}
    assert len(faults) == len(constant.mentions), faults


def test_the_budget_is_held_by_this_entry_and_not_by_a_neighbour(tmp_path: Path) -> None:
    """The interaction check: this tier's budgets were registered before its reasoning was, and a
    number some sibling entry happened to cover would be a second gate saying what one already
    said. Every other entry is run over the doctored tree and none of them notices."""
    pair = registered(REASONING_OFF)
    neighbours = tuple(
        constant for constant in crosscheck.CONSTANTS if constant.label != REASONING_OFF
    )
    for constant in neighbours:
        copied(tmp_path, constant, {})
    copied(tmp_path, pair, {FLAG_GATE: (REQUIRED, "")})
    assert crosscheck.check(tmp_path, neighbours) == []
    assert [fault.label for fault in crosscheck.check(tmp_path, (pair,))] == [REASONING_OFF]


def test_the_trail_needles_hold_over_the_files_they_name(tmp_path: Path) -> None:
    """The copy with nothing edited is green, so every red below is the edit and not the copy."""
    for label in (TRAIL_LOGGER, TRAIL_MESSAGE, TRAIL_FIELD):
        constant = registered(label)
        copied(tmp_path, constant, {})
        assert crosscheck.check_constant(tmp_path, constant) == []


def test_renaming_the_trails_logger_in_the_sink_reddens_every_document_that_states_it(
    tmp_path: Path,
) -> None:
    """The defect this entry was filed for: the name is what an operator selects the trail by, and
    three documents restate it while none of them can import it, so a rename in the sink alone
    used to leave all three instructing a reader about a logger nothing writes through."""
    constant = registered(TRAIL_LOGGER)
    renamed = SINK_LOGGER.replace("recall", "trail")
    copied(tmp_path, constant, {RECALL_SINK: (SINK_LOGGER, renamed)})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {TRAIL_LOGGER}
    assert {fault.detail.split()[0] for fault in faults} == {
        mention.path for mention in constant.mentions
    }


def test_a_document_that_stops_naming_the_trails_logger_is_a_fault(tmp_path: Path) -> None:
    """The other direction, and the one the entry's own count was stale about: the module contract
    was the third document restating this name three weeks before anybody wrote down that there
    were two, so it is held exactly like the runbooks that turn the trail on and name it."""
    constant = registered(TRAIL_LOGGER)
    reworded = ("`cortex.memory.recall` line per recall,", "line per recall,")
    copied(tmp_path, constant, {MEMORY_MODULE: reworded})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_LOGGER]
    assert MEMORY_MODULE in faults[0].detail


def test_the_trails_field_moving_in_the_sink_alone_is_a_fault(tmp_path: Path) -> None:
    """The defect this entry was filed for: the reader cuts the value out of a captured line by
    this key, so a rename in the sink leaves the one measurement behind the per-value bound's
    argument refusing every capture, in the words of a stack that wrote no trail at all."""
    constant = registered(TRAIL_FIELD)
    copied(tmp_path, constant, {RECALL_SINK: (SINK_FIELD, '"passed_over": [')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_FIELD]
    assert RECALL_SINK in faults[0].detail


def test_the_trails_message_moving_reddens_though_the_line_still_carries_the_word(
    tmp_path: Path,
) -> None:
    """The needle is the call and not the word alone, and this is what that buys.

    The sink logs through `cortex.memory.recall`, so this word sits on every rendered line twice
    and a capture would go on matching the half that did not move. A needle rendering the word
    alone would find that half in the sink too and hold nothing: the reader would keep working
    while its own comment, which says this is the message the sink writes, had stopped being true.
    """
    constant = registered(TRAIL_MESSAGE)
    copied(tmp_path, constant, {RECALL_SINK: (SINK_MESSAGE, '_logger.info("memory.ranked"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_MESSAGE]
    doctored = (tmp_path / RECALL_SINK).read_text(encoding="utf-8")
    assert "memory.recall" in doctored, "the logger goes on spelling the word that was renamed"


def test_the_reader_retuning_its_own_needle_is_the_same_fault_from_the_other_side(
    tmp_path: Path,
) -> None:
    """A reader that renamed its needle would measure nothing just as silently as a sink that
    renamed the key, so the declaring side moving alone is a fault at every place still spelling
    what the sink writes: the runbook that says which question the field answers, the module
    contract that says what is being measured, and the sink itself."""
    constant = registered(TRAIL_FIELD)
    copied(tmp_path, constant, {TRAIL_READER: ('TRAIL_FIELD = "dropped"', 'TRAIL_FIELD = "cut"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {TRAIL_FIELD}
    assert len(faults) == len(constant.mentions), faults


def test_the_trails_field_is_held_by_this_entry_and_not_by_a_neighbour(tmp_path: Path) -> None:
    """The interaction check: this sink is already a far side of the conversation entry, which
    holds a field key in the very same dict, so a rename some neighbour happened to catch would
    make this entry a second gate over what another already said. Every other entry is run over
    the doctored tree and none of them notices."""
    field = registered(TRAIL_FIELD)
    neighbours = tuple(
        constant for constant in crosscheck.CONSTANTS if constant.label != TRAIL_FIELD
    )
    for constant in neighbours:
        copied(tmp_path, constant, {})
    copied(tmp_path, field, {RECALL_SINK: (SINK_FIELD, '"passed_over": [')})
    assert crosscheck.check(tmp_path, neighbours) == []
    assert [fault.label for fault in crosscheck.check(tmp_path, (field,))] == [TRAIL_FIELD]


def test_the_trails_logger_is_held_by_this_entry_and_not_by_a_neighbour(tmp_path: Path) -> None:
    """The interaction check, and here it is the one the tied-needle addendum left standing: the
    message needle is written as the emitting call precisely because the logger's own name ends in
    the same word, so a logger renamed alone is invisible to it and to every other entry. Every
    other entry is run over the doctored tree and none of them notices."""
    logger = registered(TRAIL_LOGGER)
    neighbours = tuple(
        constant for constant in crosscheck.CONSTANTS if constant.label != TRAIL_LOGGER
    )
    for constant in neighbours:
        copied(tmp_path, constant, {})
    copied(tmp_path, logger, {RECALL_SINK: (SINK_LOGGER, SINK_LOGGER.replace("recall", "trail"))})
    assert crosscheck.check(tmp_path, neighbours) == []
    alone = crosscheck.check(tmp_path, (logger,))
    assert {fault.label for fault in alone} == {TRAIL_LOGGER}
    assert len(alone) == len(logger.mentions), alone


def test_the_audit_messages_needles_hold_over_the_files_they_name(tmp_path: Path) -> None:
    """The copy with nothing edited is green, so every red below is the edit and not the copy."""
    copied(tmp_path, registered(AUDIT_MESSAGE), {})
    assert crosscheck.check_constant(tmp_path, registered(AUDIT_MESSAGE)) == []


def test_renaming_the_audit_message_in_the_sink_alone_reddens_every_place_restating_it(
    tmp_path: Path,
) -> None:
    """The defect this entry was filed for, and the one the sample gate cannot cover.

    A rendered sample would have held the message, the level, the logger and the fields at once,
    but this sink builds its `extra=` by condition and `logcalls.py` refuses to read a field list
    off such a call, so no runbook may print one of these lines. That leaves the word restated by
    the runbook sentence telling a reader what to look for and by the suite that proves the
    shipped level, with nothing holding either to the sink.
    """
    constant = registered(AUDIT_MESSAGE)
    copied(tmp_path, constant, {AUDIT_SINK: (SINK_WORD, '_MESSAGE = "tool.dispatch"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {AUDIT_MESSAGE}
    assert {fault.detail.split()[0] for fault in faults} == {
        mention.path for mention in constant.mentions
    }


def test_the_suites_asserted_line_is_reported_against_the_word_that_moved(
    tmp_path: Path,
) -> None:
    """The interaction check: one line spends both of this trail's words, so each entry has to
    render its own half of it. The logger's needle used to spell the message as fixed text, which
    made a message renamed everywhere a fault reported against the logger, sending a reader to the
    constant that did not move and asking for an edit to registry data rather than to the tree."""
    logger, message = registered(AUDIT_LOGGER), registered(AUDIT_MESSAGE)
    moved = {LEVEL_SUITE: (ASSERTED_LINE, ASSERTED_LINE.replace("invocation", "dispatch"))}
    copied(tmp_path, logger, moved)
    copied(tmp_path, message, moved)
    assert crosscheck.check(tmp_path, (logger,)) == []
    faults = crosscheck.check(tmp_path, (message,))
    assert [fault.label for fault in faults] == [AUDIT_MESSAGE]
    assert LEVEL_SUITE in faults[0].detail


def _parts_on_disk() -> list[str]:
    """The registry's data files, read off the directory rather than off any list under test."""
    return sorted(
        path.stem
        for path in (REPO_ROOT / "scripts").glob("*couplings.py")
        if path.stem != "couplings"
    )


def _entries(part: str) -> tuple[couplings.Constant, ...]:
    """One part's own tuple, found by the naming convention every part is written under.

    The convention is asserted rather than assumed, because it is how a part is found at all and
    it is written down nowhere a `getattr` failure would send a reader: an export under another
    name raises `AttributeError: module 'foocouplings' has no attribute 'FOO_COUPLINGS'`, which
    names the attribute that is missing but neither says a rule was broken nor which half of it
    (the file's name, the tuple's) is the wrong one. Every caller here gets the sentence instead.
    """
    name = part.removesuffix("couplings").upper() + "_COUPLINGS"
    module = import_module(part)
    assert hasattr(module, name), (
        f"{part}.py exports no {name}: a registry part is a `<subject>couplings.py` holding a "
        f"`<SUBJECT>_COUPLINGS` tuple, which is how this suite finds one on disk"
    )
    exported: tuple[couplings.Constant, ...] = getattr(module, name)
    return exported


def test_the_parts_on_disk_are_exactly_what_the_registry_reads() -> None:
    """A data file nobody added to `registry.py` gates nothing; an entry in no part is unnamed.

    The registry lives in several files because the line cap keeps splitting it, and the only
    thing joining them is one import list. Forgetting a line there empties a whole subject in
    silence, which is the failure mode this scan exists to refuse, so the parts are discovered
    from disk rather than from the same list that would be wrong.

    The other direction is the one the list of parts made load-bearing. That list is the whole
    answer to what the registry is written in, so it is only an answer while every entry lives in
    a part: a `Constant` written inline in `registry.py`, or left in a module the glob above does
    not match, would be scanned exactly like the rest and sit under none of the names the
    docstring gives. The two sets are therefore equal and not nested.
    """
    parts = _parts_on_disk()
    assert parts, "the registry has no data files, which cannot be right"
    read = set(crosscheck.CONSTANTS)
    held: set[couplings.Constant] = set()
    for part in parts:
        entries = _entries(part)
        assert entries, f"{part} holds no entries"
        assert set(entries) <= read, f"{part} is not read by registry.py"
        held |= set(entries)
    stray = sorted(constant.label for constant in read - held)
    assert not stray, f"registry.py reads entries that live in no part: {stray}"


def test_the_registry_holds_each_coupling_once() -> None:
    """A coupling in two parts is checked twice, counted twice, and reported twice.

    The verdict survives that, the scan being the same question asked twice, so what breaks is
    the reading: `shape.entries` is what every mutation table in this repo opens by stating, and
    a number that double counts names a collection the registry does not have. Labels carry the
    check because the argument for not attributing a fault to its part rests on them being
    distinct, one label finding one line under one grep, and because an entry copied rather than
    moved between two parts repeats its label whether or not the copy stayed identical.
    """
    seen = Counter(constant.label for constant in crosscheck.CONSTANTS)
    repeated = sorted(label for label, count in seen.items() if count > 1)
    assert not repeated, f"the registry holds these labels more than once: {repeated}"


def test_registry_names_every_part_in_the_order_it_reads_them() -> None:
    """The parts are named in prose and nowhere else, so the prose is held to the directory.

    `registry.shape` counts places and not parts on purpose, which leaves the list in
    `registry.py`'s docstring as the whole answer to what the registry is written in. A list that
    is the answer has to be complete, or the next part lands unnamed and the answer is short by
    one without saying so; and its order has to be the order the same docstring claims for it,
    which is the order the tuple joins the parts in and so the order faults are reported in.
    """
    named = re.findall(r"^- `(\w+)` ", registry.__doc__ or "", re.MULTILINE)
    assert named, "registry.py names no part, so nothing says what the registry is written in"
    # A part whose entries never reached the tuple sorts last rather than raising, so the test
    # above stays the one that reports it and this one reports the list instead of a traceback.
    position = {constant: index for index, constant in enumerate(crosscheck.CONSTANTS)}
    read_in_order = sorted(
        _parts_on_disk(), key=lambda part: position.get(_entries(part)[0], len(position))
    )
    assert named == read_in_order


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


def test_every_registered_mention_renders_something_the_registry_fills() -> None:
    """A template that renders neither the value nor a name finds itself in any file."""
    for constant in crosscheck.CONSTANTS:
        for mention in constant.mentions:
            renders_name = crosscheck.NAME_PLACEHOLDER in mention.template
            assert crosscheck.PLACEHOLDER in mention.template or renders_name, constant.label
            assert renders_name == (mention.name is not None), constant.label


def test_the_registry_spends_at_least_one_rendered_name() -> None:
    """A field no entry sets is a dead wire, and this repo declines those."""
    named = [
        mention
        for constant in crosscheck.CONSTANTS
        for mention in constant.mentions
        if mention.name is not None
    ]
    assert named
    assert any(crosscheck.PLACEHOLDER not in mention.template for mention in named)


# Not three forms but two plus a widening of a third, all unexercised in the same way: the
# reducer refused a leading sign until two compose defaults turned out to spell one.
WIDENINGS: list[tuple[str, Callable[[values.Value], bool]]] = [
    ("a decimal", lambda value: isinstance(value, values.Digits)),
    ("a boolean", lambda value: isinstance(value, values.Truth)),
    ("a signed integer", lambda value: isinstance(value, int) and value < 0),
]


@pytest.mark.parametrize(("form", "reads"), WIDENINGS)
def test_the_registry_reduces_every_form_the_reducer_was_widened_for(
    form: str, reads: Callable[[values.Value], bool]
) -> None:
    """A value form no entry spells is the same dead wire an unused comparator is."""
    read = [
        crosscheck.read_value(REPO_ROOT, site)
        for constant in crosscheck.CONSTANTS
        for site in constant.sites
    ]
    assert any(reads(value) for value in read), form


def test_the_registry_exercises_every_spelling() -> None:
    """A spelling no entry asks for is a widened gate that cannot fail, same as a comparator."""
    spelled = {
        mention.spelling for constant in crosscheck.CONSTANTS for mention in constant.mentions
    }
    assert spelled == set(couplings.Spelling)


def test_the_registry_exercises_every_relation() -> None:
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


# ── the registry's own shape, which is read and never asserted ─────────────────
#
# Four numbers over one walk of the same tuple the scan already walks. Nothing here pins what the
# real registry's shape IS: that would be a gate over the documents quoting it, which is the
# exclusion a document describing this gate has always had. What is pinned is that each number
# counts the thing it is named for, which is the only way a mutation table's "one of N" means
# anything.

_SHAPED = (
    crosscheck.Constant(
        label="two sites and nothing spent",
        why="both enforcers must agree",
        sites=(crosscheck.Site("a.rs", "A"), crosscheck.Site("a.py", "A")),
    ),
    crosscheck.Constant(
        label="one spend counted, one not",
        why="the runbook restates it",
        sites=(crosscheck.Site("b.py", "B"),),
        mentions=(
            couplings.Mention(path="b.md", template="B={value}"),
            couplings.Mention(path="b.yml", template="B={value}", occurrences=2),
        ),
    ),
    crosscheck.Constant(
        label="three spends, one counted",
        why="the stylesheet spends it",
        sites=(crosscheck.Site("c.ts", "C"),),
        mentions=(
            couplings.Mention(path="c.css", template="{value}"),
            couplings.Mention(path="d.css", template="{value}"),
            couplings.Mention(path="e.css", template="{value}", occurrences=3),
        ),
    ),
)


def test_shape_counts_each_kind_of_place_separately() -> None:
    """Four distinct numbers, so a field counting the wrong collection cannot pass unnoticed."""
    assert registry.shape(_SHAPED) == registry.Shape(entries=3, sites=4, mentions=5, counted=2)


def test_shape_of_an_empty_registry_is_all_zeros() -> None:
    """What a rename that emptied the registry would print: a scan agreeing with nothing."""
    assert registry.shape(()) == registry.Shape(entries=0, sites=0, mentions=0, counted=0)


def test_shape_counts_a_pinned_count_once_and_not_its_occurrences() -> None:
    """`counted` is how many mentions pin a number, never the sum of the numbers they pin."""
    pinned = registry.shape(_SHAPED).counted
    assert pinned == 2
    assert pinned != sum(
        mention.occurrences or 0 for constant in _SHAPED for mention in constant.mentions
    )


# ── the CLI ────────────────────────────────────────────────────────────────────


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert crosscheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "crosscheck OK" in capsys.readouterr().out


def test_main_states_the_registrys_shape_on_success(capsys: pytest.CaptureFixture[str]) -> None:
    """The success line carries all four numbers, which is the whole deliverable here."""
    assert crosscheck.main(["--root", str(REPO_ROOT)]) == 0
    size = registry.shape(crosscheck.CONSTANTS)
    out = capsys.readouterr().out
    assert f"{size.entries} cross-tree constant(s)" in out
    assert f"{size.sites} declaring site(s)" in out
    assert f"{size.mentions} mention(s)" in out
    assert f"{size.counted} of them pinned to a count" in out


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
