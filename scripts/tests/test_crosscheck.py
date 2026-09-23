import re
from collections import Counter
from collections.abc import Callable
from importlib import import_module
from pathlib import Path

import pytest

import couplings
import crosscheck
import linereadings
import logcalls
import registry
import searchtexts
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
    """Write the two files the `BYTE_CEILING` entry compares, one declaration per language."""
    declaration = f"pub const MAX_CAPTURE_BYTES: usize = {rust};\n"
    (root / "body.rs").write_text(declaration, encoding="utf-8")
    (root / "brain.py").write_text(f"MAX_IMAGE_BYTES = {python}\n", encoding="utf-8")


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
    rust = 'const RPC_TOKEN_HEADER: &str = "x-cortex-seam-token";\n'
    python = 'RPC_TOKEN_HEADER = "x-cortex-seam-token"  # noqa: S105 - the header NAME\n'
    (tmp_path / "auth.rs").write_text(rust, encoding="utf-8")
    (tmp_path / "seam.py").write_text(python, encoding="utf-8")
    from_rust = crosscheck.read_value(tmp_path, crosscheck.Site("auth.rs", "RPC_TOKEN_HEADER"))
    from_python = crosscheck.read_value(tmp_path, crosscheck.Site("seam.py", "RPC_TOKEN_HEADER"))
    assert from_rust == from_python == "x-cortex-seam-token"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("decl.rs", "pub const MAX_CAPTURE_BYTES_EXTRA: usize = 1;\n"),
        ("decl.py", "MAX_CAPTURE_BYTES_EXTRA = 1\n"),
        ("decl.py", "    MAX_CAPTURE_BYTES = 1\n"),
        ("decl.rs", "let MAX_CAPTURE_BYTES: usize = 1;\n"),
        ("decl.ts", "const MAX_CAPTURE_BYTES_EXTRA = 1;\n"),
        ("decl.ts", "  const MAX_CAPTURE_BYTES = 1;\n"),
        ("decl.ts", "let MAX_CAPTURE_BYTES = 1;\n"),
    ],
)
def test_read_value_fails_closed_when_the_name_is_gone(
    tmp_path: Path, name: str, text: str
) -> None:
    (tmp_path / name).write_text(text, encoding="utf-8")
    site = crosscheck.Site(name, "MAX_CAPTURE_BYTES")
    with pytest.raises(crosscheck.CrossCheckError, match="declares no MAX_CAPTURE_BYTES"):
        crosscheck.read_value(tmp_path, site)


def test_read_value_fails_closed_on_two_declarations(tmp_path: Path) -> None:
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
    (tmp_path / "sessionState.ts").write_text("const TITLE_MAX = 48;\n", encoding="utf-8")
    (tmp_path / "sessions.py").write_text("TITLE_MAX = 48\n", encoding="utf-8")
    from_ts = crosscheck.read_value(tmp_path, crosscheck.Site("sessionState.ts", "TITLE_MAX"))
    from_py = crosscheck.read_value(tmp_path, crosscheck.Site("sessions.py", "TITLE_MAX"))
    assert from_ts == from_py == 48


def test_check_constant_ties_two_forms_of_one_number(tmp_path: Path) -> None:
    _tie(tmp_path, rust="6 * 1024 * 1024", python="6291456")
    assert crosscheck.check_constant(tmp_path, BYTE_CEILING) == []


def test_check_constant_catches_the_drift_this_gate_exists_for(tmp_path: Path) -> None:
    _tie(tmp_path, rust="8 * 1024 * 1024", python="6 * 1024 * 1024")
    (fault,) = crosscheck.check_constant(tmp_path, BYTE_CEILING)
    assert fault.label == "a ceiling"
    assert "body.rs: MAX_CAPTURE_BYTES = 8388608" in fault.detail
    assert "brain.py: MAX_IMAGE_BYTES = 6291456" in fault.detail
    assert BYTE_CEILING.why in fault.detail


def test_check_constant_reports_a_broken_site_rather_than_agreement(tmp_path: Path) -> None:
    (tmp_path / "brain.py").write_text("MAX_IMAGE_BYTES = 6291456\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, BYTE_CEILING)
    assert "cannot read body.rs" in fault.detail


def test_check_constant_reports_every_broken_site(tmp_path: Path) -> None:
    details = [fault.detail for fault in crosscheck.check_constant(tmp_path, BYTE_CEILING)]
    assert [detail.split(":")[0] for detail in details] == [
        "cannot read body.rs",
        "cannot read brain.py",
    ]


def test_check_constant_refuses_a_registry_entry_that_compares_nothing() -> None:
    lonely = crosscheck.Constant(
        label="a lonely value",
        why="nothing",
        sites=(crosscheck.Site("brain.py", "A"),),
    )
    (fault,) = crosscheck.check_constant(Path(), lonely)
    assert "fewer than two places" in fault.detail


def test_check_constant_refuses_an_entry_with_nothing_to_read_the_value_from() -> None:
    mentions_only = crosscheck.Constant(
        label="an unestablished value",
        why="nothing",
        sites=(),
        mentions=(crosscheck.Mention("a.css", "var({value})"), crosscheck.Mention("b.css", "x")),
    )
    (fault,) = crosscheck.check_constant(Path(), mentions_only)
    assert "names no declaring site" in fault.detail


def test_check_constant_refuses_a_mention_on_an_ordering() -> None:
    muddled = ORDERING._replace(mentions=(crosscheck.Mention("a.css", "{value}"),))
    (fault,) = crosscheck.check_constant(Path(), muddled)
    assert "no one value a mention could write" in fault.detail


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
    _order(tmp_path, lower, upper)
    assert crosscheck.check_constant(tmp_path, ORDERING) == []


def test_an_ordering_fails_when_the_lower_bound_climbs_past_the_upper(tmp_path: Path) -> None:
    _order(tmp_path, "16384", "8192")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "not non-decreasing in registry order" in fault.detail
    assert "MAX_EDGE_CEILING = 16384" in fault.detail
    assert ORDERING.why in fault.detail


def test_the_same_sites_under_an_equality_would_be_a_fault(tmp_path: Path) -> None:
    _order(tmp_path, "4096", "8192")
    equal = ORDERING._replace(relation=crosscheck.Relation.EQUAL)
    (fault,) = crosscheck.check_constant(tmp_path, equal)
    assert "not identical" in fault.detail


def test_an_ordering_over_strings_is_refused(tmp_path: Path) -> None:
    (tmp_path / "body.rs").write_text('const MAX_EDGE_CEILING: &str = "a";\n', encoding="utf-8")
    (tmp_path / "brain.py").write_text('MAX_IMAGE_EDGE = "b"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "an ordering compares integers" in fault.detail


def test_an_ordering_over_decimals_is_refused_too(tmp_path: Path) -> None:
    _order(tmp_path, "4.0", "8.0")
    (fault,) = crosscheck.check_constant(tmp_path, ORDERING)
    assert "an ordering compares integers" in fault.detail


def _two_python_bounds(root: Path, lower: str, upper: str) -> crosscheck.Constant:
    """Return an ordering over two Python files, for values too large for a `u32`."""
    (root / "one.py").write_text(f"LOWER = {lower}\n", encoding="utf-8")
    (root / "other.py").write_text(f"UPPER = {upper}\n", encoding="utf-8")
    return ORDERING._replace(
        sites=(crosscheck.Site("one.py", "LOWER"), crosscheck.Site("other.py", "UPPER"))
    )


def test_an_ordering_over_booleans_is_refused_too(tmp_path: Path) -> None:
    ordering = _two_python_bounds(tmp_path, "False", "True")
    (fault,) = crosscheck.check_constant(tmp_path, ordering)
    assert "an ordering compares integers" in fault.detail


@pytest.mark.parametrize(("lower", "upper"), [("-1", "0"), ("-2", "-1")])
def test_an_ordering_sorts_a_signed_bound_as_the_number_it_is(
    tmp_path: Path, lower: str, upper: str
) -> None:
    ordering = _two_python_bounds(tmp_path, lower, upper)
    assert crosscheck.check_constant(tmp_path, ordering) == []


def test_an_ordering_catches_a_signed_bound_that_climbed(tmp_path: Path) -> None:
    ordering = _two_python_bounds(tmp_path, "-1", "-2")
    (fault,) = crosscheck.check_constant(tmp_path, ordering)
    assert "not non-decreasing in registry order" in fault.detail


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
    """Write a Rust `&str` constant and the Python `frozenset` it must be a member of."""
    declaration = f'pub const CAPTURE_MIME: &str = "{produced}";\n'
    (root / "body.rs").write_text(declaration, encoding="utf-8")
    members = ", ".join(f'"{one}"' for one in allowed)
    (root / "brain.py").write_text(f"ALLOWED_MIME_TYPES = frozenset({{{members}}})\n", "utf-8")


def test_a_membership_holds_wherever_in_the_collection_the_value_sits(tmp_path: Path) -> None:
    _allow(tmp_path, "image/png", "image/png", "image/jpeg", "image/webp")
    assert crosscheck.check_constant(tmp_path, MEMBERSHIP) == []


def test_a_membership_fails_when_the_collection_drops_the_value(tmp_path: Path) -> None:
    _allow(tmp_path, "image/png", "image/jpeg", "image/webp")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "not members of the collection the last site declares" in fault.detail
    assert "body.rs: CAPTURE_MIME = 'image/png'" in fault.detail
    assert MEMBERSHIP.why in fault.detail


def test_a_membership_fails_when_the_value_leaves_the_collection(tmp_path: Path) -> None:
    _allow(tmp_path, "image/gif", "image/png", "image/jpeg")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "body.rs: CAPTURE_MIME = 'image/gif'" in fault.detail


def test_a_membership_needs_a_collection_at_the_last_site(tmp_path: Path) -> None:
    _allow(tmp_path, "image/png")
    (tmp_path / "brain.py").write_text('ALLOWED_MIME_TYPES = "image/png"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MEMBERSHIP)
    assert "a membership needs a collection at the last site" in fault.detail


def test_the_same_sites_under_an_equality_would_be_a_fault_too(tmp_path: Path) -> None:
    _allow(tmp_path, "image/png", "image/png", "image/jpeg")
    equal = MEMBERSHIP._replace(relation=crosscheck.Relation.EQUAL)
    (fault,) = crosscheck.check_constant(tmp_path, equal)
    assert "not identical" in fault.detail


MENTIONED = crosscheck.Constant(
    label="a spent value",
    why="the stylesheet reads back what the module publishes",
    sites=(crosscheck.Site("budget.ts", "CEILING_PROPERTY"),),
    mentions=(crosscheck.Mention("overlay.css", "var({value},"),),
)


def _spend(root: Path, declared: str, written: str) -> None:
    (root / "budget.ts").write_text(f'const CEILING_PROPERTY = "{declared}";\n', encoding="utf-8")
    (root / "overlay.css").write_text(f".panel {{ height: var({written}, 100vh); }}\n", "utf-8")


def test_a_mention_found_in_the_shape_it_names_is_tied(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", written="--ceiling")
    assert crosscheck.check_constant(tmp_path, MENTIONED) == []


def test_a_rename_on_the_declaring_side_leaves_the_search_text_unfound(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--roof", written="--ceiling")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "does not write 'var(--roof,'" in fault.detail


def test_a_rename_on_the_spending_side_leaves_it_unfound_too(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", written="--roof")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "does not write 'var(--ceiling,'" in fault.detail


def _ported(template: str) -> crosscheck.Constant:
    """Return an entry for a port declared in Python and used in a compose port mapping."""
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


def test_a_number_a_longer_one_merely_contains_is_not_written(tmp_path: Path) -> None:
    _publish(tmp_path, declared="5005", host="50051", container="50051")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}"))
    assert "does not write '127.0.0.1:5005' as a token of its own" in fault.detail
    assert "having it only inside a longer token" in fault.detail


def test_a_template_that_fixes_only_the_host_half_leaves_the_other_free(tmp_path: Path) -> None:
    _publish(tmp_path, declared="50051", host="50051", container="50052")
    assert crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}")) == []
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "does not write '127.0.0.1:50051:50051'" in fault.detail


def _publish_on(root: Path, interface: str) -> None:
    """Write the port declaration and a compose mapping with the given host interface."""
    (root / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (root / "stack.yml").write_text(f'      - "{interface}:50051:50051"\n', encoding="utf-8")


def test_a_moved_neighbour_is_reported_as_shape_and_not_as_this_value(tmp_path: Path) -> None:
    _publish_on(tmp_path, "127.0.0.2")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "with the most of it on line 1, 20 of its 21 characters" in fault.detail
    assert "(its opening '127.0.0.' and its closing ':50051:50051')" in fault.detail
    assert "the file does still write '50051' as a token of its own" in fault.detail
    assert "the constant to change may not be the one named here" in fault.detail


def test_a_moved_value_is_reported_as_absent_and_blames_no_neighbour(tmp_path: Path) -> None:
    _publish(tmp_path, declared="50052", host="50051", container="50051")
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}"))
    assert "on line 1, 14 of its 15 characters (its opening '127.0.0.1:5005')," in fault.detail
    assert "the file does not write '50052' as a token of its own either" in fault.detail


def test_a_value_left_only_inside_a_decimal_is_not_read_as_still_being_written(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.py").write_text("DEFAULT_STOP_GRACE_S = 10\n", encoding="utf-8")
    (tmp_path / "swap.md").write_text("answered in **10.09 s**, so the\n", encoding="utf-8")
    graced = crosscheck.Constant(
        label="the grace a child gets before it is killed",
        why="an eviction pays this whole grace when the child has a request in flight",
        sites=(crosscheck.Site("config.py", "DEFAULT_STOP_GRACE_S"),),
        mentions=(crosscheck.Mention("swap.md", "{value} s"),),
    )
    (fault,) = crosscheck.check_constant(tmp_path, graced)
    assert "does not write '10 s' as a token of its own" in fault.detail
    assert (
        "on line 1, 4 of its 4 characters (its opening '10' and its closing ' s')" in fault.detail
    )
    assert "the file does not write '10' as a token of its own either" in fault.detail


def test_a_file_containing_no_part_of_the_search_text_has_no_run_to_report(tmp_path: Path) -> None:
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (tmp_path / "overlay.css").write_text(".panel { height: 100px; }\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "with less than half of it on any line" in fault.detail
    assert "does not write '--ceiling' as a token of its own either" in fault.detail


_GRACED = crosscheck.Constant(
    label="the grace a child gets before it is killed",
    why="an eviction pays this whole grace when the child has a request in flight",
    sites=(crosscheck.Site("config.py", "DEFAULT_STOP_GRACE_S"),),
    mentions=(crosscheck.Mention("swap.md", "the full grace ({value} s)"),),
)


def _graced(root: Path, swap: str) -> None:
    """Write a stop grace of 11 seconds, beside the runbook text the caller passes in."""
    (root / "config.py").write_text("DEFAULT_STOP_GRACE_S = 11\n", encoding="utf-8")
    (root / "swap.md").write_text(swap, encoding="utf-8")


def test_a_yes_reads_back_the_line_it_read_the_value_on(tmp_path: Path) -> None:
    _graced(
        tmp_path,
        "the full grace (10 s) is paid when a request is in flight\n"
        "\n"
        "the cortex still holds ~11 GB of it while it dies\n",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "with the most of it on line 1, 20 of its 21 characters" in fault.detail
    assert "the file does still write '11' as a token of its own, once on line 3" in fault.detail
    assert "which reads 'the cortex still holds ~11 GB of it while it dies'" in fault.detail
    assert "and no run stops on that line, so what moved is not settled here" in fault.detail
    assert "likely shape" not in fault.detail


def test_a_last_line_with_no_newline_is_still_read_back_whole(tmp_path: Path) -> None:
    _graced(tmp_path, "the full grace (10 s) is paid\n\nthe cortex holds ~11 GB")
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "once on line 3, which reads 'the cortex holds ~11 GB'" in fault.detail


def test_the_run_is_measured_where_it_stops_and_not_where_it_starts(tmp_path: Path) -> None:
    _graced(
        tmp_path,
        "11 GB of it is still held\nand the full grace (10 s) is paid\nwhich leaves 11 free\n",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _GRACED)
    assert "with the most of it on line 2, 20 of its 21 characters" in fault.detail
    assert "(its opening 'the full grace (1' and its closing ' s)')" in fault.detail
    assert "in 2 places, the nearest to that run on line 3" in fault.detail
    assert "which reads 'which leaves 11 free'" in fault.detail


def test_a_value_in_several_places_is_counted_and_read_nearest_the_run(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(
        "# the brain answered on 50051 before the move\n\n\n\n\n\n\n"
        '      - "127.0.0.2:50051:50051"\n',
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _ported("127.0.0.1:{value}:{value}"))
    assert "with the most of it on line 8, 20 of its 21 characters" in fault.detail
    assert "in 3 places, the nearest to that run on line 8" in fault.detail
    assert "which reads '- \"127.0.0.2:50051:50051\"'" in fault.detail


def test_a_run_found_in_several_places_names_the_stop_nearest_the_form(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(
        '      - "127.0.0.1:6379:6379"\n\n\n\n\n\n\n      - "127.0.0.1:9090:50051"\n',
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _ported('127.0.0.1:{value}:{value}"\n'))
    assert "with no more of it than '127.0.0.1:'" in fault.detail
    assert "which stops in 2 places, the nearest to that form on line 8" in fault.detail
    assert "still write '50051' as a token of its own, once on line 8" in fault.detail


_THREADED = crosscheck.Constant(
    label="a thread count",
    why="the flag and the substitution under it are one search_text",
    sites=(crosscheck.Site("config.py", "THREADS"),),
    mentions=(crosscheck.Mention("stack.yml", '- "--threads"\n      - "{value}"'),),
)


@pytest.mark.parametrize(
    ("stack", "expected"),
    [
        ("ctx: 8\n", "with no part of it; the file does not write '4'"),
        (
            '      - "--threads"\n      - "8"\n',
            'with no more of it than \'- "--threads"\\n      - "\', which stops on line 2; '
            "the file does not write '4'",
        ),
        (
            '- "--threads"\n  - "8"\n- "--threads"\n  - "9"\n',
            "which stops in 2 places, the first on line 2; the file does not write '4'",
        ),
    ],
)
def test_a_search_text_holding_a_newline_is_read_over_the_whole_file(
    tmp_path: Path, stack: str, expected: str
) -> None:
    (tmp_path / "config.py").write_text("THREADS = 4\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(stack, encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, _THREADED)
    assert expected in fault.detail
    assert "on any line" not in fault.detail


def test_a_value_in_several_places_with_no_run_at_all_is_read_at_the_first(tmp_path: Path) -> None:
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (tmp_path / "overlay.css").write_text(
        ".panel { height: --ceiling; }\n.rail { width: --ceiling; }\n", encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "with less than half of it on any line" in fault.detail
    assert "in 2 places, the first on line 1" in fault.detail
    assert "which reads '.panel { height: --ceiling; }'" in fault.detail
    assert "and no run stops on that line, so what moved is not settled here" in fault.detail
    assert "likely shape" not in fault.detail


_KINDED = crosscheck.Constant(
    label="the kind word a sidecar declares a sender under",
    why="the brain admits a declaration only when its kind is a claimed member's value",
    sites=(crosscheck.Site("server.py", "_SENDER_KIND"),),
    mentions=(crosscheck.Mention("provenance.py", '{name} = "{value}"', name="SENDER"),),
)


def test_a_word_still_written_in_prose_settles_nothing_about_what_moved(tmp_path: Path) -> None:
    (tmp_path / "server.py").write_text('_SENDER_KIND = "sender"\n', encoding="utf-8")
    (tmp_path / "provenance.py").write_text(
        '"""Eviction by sender must not sweep a URI."""\n\n\nSENDER = "from"\n', encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, _KINDED)
    assert "with the most of it on line 4, 11 of its 17 characters" in fault.detail
    assert "(its opening 'SENDER = \"' and its closing '\"')" in fault.detail
    assert "does still write 'sender' as a token of its own, once on line 1" in fault.detail
    assert "and no run stops on that line, so what moved is not settled here" in fault.detail
    assert "likely shape" not in fault.detail


def test_a_word_written_where_the_run_stops_is_read_as_the_shape_moving(tmp_path: Path) -> None:
    (tmp_path / "server.py").write_text('_SENDER_KIND = "sender"\n', encoding="utf-8")
    (tmp_path / "provenance.py").write_text(
        '"""Eviction by sender must not sweep a URI."""\n\n\nSENDERS = "sender"\n', encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, _KINDED)
    assert "does still write 'sender' as a token of its own, in 2 places" in fault.detail
    assert "the nearest to that run on line 4" in fault.detail
    assert (
        "so what moved is likely shape this search text has rather than this value" in fault.detail
    )


def _row(before: int, after: int) -> tuple[str, int, int]:
    """Return a table row containing `2048` at a chosen offset, with that offset and its end."""
    line = f"| {'w' * before} | 2048 | {'x' * after} |"
    return line, line.index("2048"), line.index("2048") + len("2048")


@pytest.mark.parametrize(
    ("before", "after", "opens", "closes"),
    [
        (2, 2, False, False),
        (200, 200, True, True),
        (2, 400, False, True),
        (400, 2, True, False),
    ],
)
def test_a_quote_is_windowed_only_where_the_line_runs_past_it(
    before: int, after: int, *, opens: bool, closes: bool
) -> None:
    line, start, end = _row(before, after)
    read = linereadings.quote(line, start, end)
    assert "2048" in read
    assert len(read) <= linereadings.QUOTED_WIDTH + 2 * len(linereadings.TRIMMED)
    assert read.startswith(linereadings.TRIMMED) is opens
    assert read.endswith(linereadings.TRIMMED) is closes


def test_a_search_text_that_renders_only_a_name_is_read_on_that_name(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--ease", "--ease")
    spent = RESTATED._replace(
        mentions=(RESTATED.mentions[0], RESTATED.mentions[1]._replace(occurrences=None)),
    )
    (fault,) = crosscheck.check_constant(tmp_path, spent)
    assert "does not write 'var(--roll)' as a token of its own" in fault.detail
    assert "with the most of it on 2 lines, 7 of its 11 characters" in fault.detail
    assert "(its opening 'var(--' and its closing ')') each" in fault.detail
    assert "the nearest to that form on line 2" in fault.detail
    assert "does still write '--roll' as a token of its own, once on line 1" in fault.detail
    assert searchtexts.APART in fault.detail


UNDER_A_FIELD = crosscheck.Constant(
    label="a word written under a neighbour's field",
    why="the sidecar declares its sender under this word and the brain admits only that word",
    sites=(crosscheck.Site("server.py", "_SENDER_KIND"),),
    mentions=(
        crosscheck.Mention("core.py", '{name} = "{value}"', name="SENDER"),
        crosscheck.Mention("server.py", "_KIND_FIELD: {name},", name="_SENDER_KIND"),
    ),
)


def _declare(root: Path, field: str) -> None:
    """Write a sidecar declaring its sender under ``field``, and the core value it must match."""
    (root / "core.py").write_text('SENDER = "sender"\n', encoding="utf-8")
    (root / "server.py").write_text(
        '_SENDER_KIND = "sender"\n'
        f'{field} = "kind"\n'
        f"DECLARATION = {{_SOURCE_KEY: {{{field}: _SENDER_KIND, _VALUE_FIELD: sender}}}}\n",
        encoding="utf-8",
    )


def test_a_name_whose_shape_is_a_neighbours_binding_reports_the_shape_as_the_mover(
    tmp_path: Path,
) -> None:
    _declare(tmp_path, "_KIND_FIELD")
    assert crosscheck.check_constant(tmp_path, UNDER_A_FIELD) == []
    _declare(tmp_path, "_KIND_NAME")
    (fault,) = crosscheck.check_constant(tmp_path, UNDER_A_FIELD)
    assert "does not write '_KIND_FIELD: _SENDER_KIND,' as a token of its own" in fault.detail
    assert "does still write '_SENDER_KIND' as a token of its own" in fault.detail
    assert searchtexts.MET.format(part=searchtexts.NAME) in fault.detail


@pytest.mark.parametrize(
    ("search_text", "text", "found"),
    [
        ("50051", "  - 50051\n", True),
        ("50051", "  - 500511\n", False),
        ("50051", "  - 150051\n", False),
        ("var(--ceiling,", "height: var(--ceiling, 100vh);", True),
        ("--ease: linear", "--ease: linearity;", False),
        ("[data-morphing", ".view:has([data-morphing]) {", True),
    ],
)
def test_a_search_text_is_bounded_at_whichever_edge_is_a_word(
    search_text: str, text: str, *, found: bool
) -> None:
    assert bool(crosscheck.bounded(search_text).search(text)) is found


@pytest.mark.parametrize(
    ("search_text", "text", "found"),
    [
        ("2048", "the shipped edge is 2048.", True),
        ("2048", "resampled to 2048.5 px", False),
        ("2048", "measured at 0.2048 of the edge", False),
        ("2048", "the ceiling. 2048 is the edge", True),
        ("6291456", "outside `1..6291456`", True),
        ("10", "the full grace (10 s) was paid", True),
        ("10", "answered in **10.09 s**", False),
        ("10", "stop answered in **0.10 s**", False),
        ("insecure_channel(", "grpc.insecure_channel(", True),
        ("auto", "tiers.2.auto is the shipped mode", True),
        ("tiers", "tiers.2 is the deep one", True),
        ("--ease: linear", "0.--ease: linear;", True),
    ],
)
def test_a_point_between_two_digits_is_inside_a_number_and_not_a_full_stop(
    search_text: str, text: str, *, found: bool
) -> None:
    assert bool(crosscheck.bounded(search_text).search(text)) is found


def test_a_mention_on_a_file_that_cannot_be_read_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "budget.ts").write_text('const CEILING_PROPERTY = "--ceiling";\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, MENTIONED)
    assert "cannot read overlay.css" in fault.detail


def test_a_mention_template_that_renders_nothing_is_refused(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", written="--ceiling")
    blind = MENTIONED._replace(mentions=(crosscheck.Mention("overlay.css", ".panel"),))
    (fault,) = crosscheck.check_constant(tmp_path, blind)
    assert "renders neither {value} nor {name}" in fault.detail


def test_every_mention_is_reported_rather_than_only_the_first(tmp_path: Path) -> None:
    _spend(tmp_path, declared="--ceiling", written="--roof")
    both = MENTIONED._replace(
        mentions=(*MENTIONED.mentions, crosscheck.Mention("gone.css", "var({value})"))
    )
    details = [fault.detail for fault in crosscheck.check_constant(tmp_path, both)]
    assert len(details) == 2
    assert "cannot read gone.css" in details[1]


def _compare(root: Path, declared: str, *written: str) -> None:
    """Write a state string declared in Python and compared against in a component, one per line."""
    (root / "channels.py").write_text(f'STATE = "{declared}"\n', encoding="utf-8")
    lines = "".join(f'  aria-label={{s === "{one}" ? "x" : undefined}}\n' for one in written)
    (root / "Message.tsx").write_text(f"<span\n{lines}/>\n", encoding="utf-8")


def _counted(occurrences: int | None) -> crosscheck.Constant:
    return crosscheck.Constant(
        label="a compared state",
        why="both comparisons decide on the same state",
        sites=(crosscheck.Site("channels.py", "STATE"),),
        mentions=(crosscheck.Mention("Message.tsx", 's === "{value}"', occurrences),),
    )


def test_a_counted_mention_holds_when_the_whole_set_is_written(tmp_path: Path) -> None:
    _compare(tmp_path, "thinking", "thinking", "thinking")
    assert crosscheck.check_constant(tmp_path, _counted(2)) == []


def test_a_half_applied_rename_passes_a_presence_check_and_fails_a_counted_one(
    tmp_path: Path,
) -> None:
    _compare(tmp_path, "deliberating", "deliberating", "thinking")
    assert crosscheck.check_constant(tmp_path, _counted(None)) == []
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    form = "writes 's === \"deliberating\"' as a token of its own: found 1 (on line 2), set to 2"
    assert form in fault.detail


def test_a_counted_mention_that_finds_nothing_reads_like_a_presence_check(tmp_path: Path) -> None:
    (tmp_path / "channels.py").write_text('STATE = "thinking"\n', encoding="utf-8")
    (tmp_path / "Message.tsx").write_text(
        '<span\n  aria-label={state === "thinking" ? "x" : undefined}\n/>\n', encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    assert "does not write 's === \"thinking\"' as a token of its own" in fault.detail
    assert "the file does still write 'thinking' as a token of its own" in fault.detail
    assert "the registry sets 2 occurrences, so move the whole set" in fault.detail
    assert "found 0" not in fault.detail


def test_a_counted_mention_fails_on_one_occurrence_too_many(tmp_path: Path) -> None:
    _compare(tmp_path, "thinking", "thinking", "thinking", "thinking")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    assert "found 3 (on lines 2, 3 and 4), set to 2; move the whole set" in fault.detail
    assert "outside those" not in fault.detail


def test_a_counted_mention_on_a_file_that_cannot_be_read_is_a_fault(tmp_path: Path) -> None:
    (tmp_path / "channels.py").write_text('STATE = "thinking"\n', encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(2))
    assert "cannot read Message.tsx" in fault.detail


@pytest.mark.parametrize("occurrences", [0, -1])
def test_a_count_below_one_is_refused(tmp_path: Path, occurrences: int) -> None:
    _compare(tmp_path, "thinking", "thinking")
    (fault,) = crosscheck.check_constant(tmp_path, _counted(occurrences))
    assert f"sets {occurrences} occurrences, which ties nothing" in fault.detail


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
    """Write a duration declared in TypeScript, repeated on `:root` and used by two rules."""
    (root / "morph.ts").write_text("export const ROLL_MS = 300;\n", encoding="utf-8")
    rules = "".join(f".s{i} {{ transition: var({one}); }}\n" for i, one in enumerate(spent))
    (root / "overlay.css").write_text(f":root {{ {declared}: 300ms; }}\n{rules}", "utf-8")


def test_a_named_mention_holds_when_the_sheet_declares_and_spends_one_property(
    tmp_path: Path,
) -> None:
    _restate(tmp_path, "--roll", "--roll", "--roll")
    assert crosscheck.check_constant(tmp_path, RESTATED) == []


def test_a_mistyped_spend_fails_where_a_rendered_value_never_reached_it(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--roll", "--rol")
    value_only = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "--roll: {value}ms;"),)
    )
    assert crosscheck.check_constant(tmp_path, value_only) == []
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert (
        "writes 'var(--roll)' as a token of its own: found 1 (on line 2), set to 2" in fault.detail
    )


def test_a_spend_that_pays_a_neighbouring_property_is_a_spend_short(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--roll", "--ease")
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert "found 1 (on line 2), set to 2" in fault.detail


def test_renaming_the_declared_property_leaves_the_declaration_unfound(tmp_path: Path) -> None:
    _restate(tmp_path, "--cadence", "--roll", "--roll")
    (fault,) = crosscheck.check_constant(tmp_path, RESTATED)
    assert "does not write '--roll: 300ms;' as a token of its own" in fault.detail


def test_a_template_rendering_a_name_the_mention_does_not_have_is_refused(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--roll", "--roll")
    nameless = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "{name}: {value}ms;"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, nameless)
    assert "renders a name the mention does not have" in fault.detail


def test_a_name_the_template_renders_nowhere_is_refused(tmp_path: Path) -> None:
    _restate(tmp_path, "--roll", "--roll", "--roll")
    unspent = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "--roll: {value}ms;", name="--roll"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, unspent)
    assert "renders it nowhere" in fault.detail


def test_a_spent_name_no_mention_pays_the_value_under_is_refused(tmp_path: Path) -> None:
    unpaid = RESTATED._replace(
        mentions=(crosscheck.Mention("overlay.css", "var({name})", name="--roll"),)
    )
    (fault,) = crosscheck.check_constant(tmp_path, unpaid)
    assert "no site declares that name and no mention renders the value under it" in fault.detail


HANDED = crosscheck.Constant(
    label="a handed message",
    why="the runbook restates the word, and the call spends the binding by name",
    sites=(crosscheck.Site("sink.py", "_MESSAGE"),),
    mentions=(
        crosscheck.Mention("runbook.md", "a bare `{value}` message"),
        crosscheck.Mention("sink.py", "_logger.info({name},", name="_MESSAGE"),
    ),
)


def _hand(root: Path, call: str) -> None:
    """Write a module whose log message is a constant above one call, and a runbook quoting it."""
    (root / "sink.py").write_text(f'_MESSAGE = "tool.invocation"\n{call}\n', encoding="utf-8")
    (root / "runbook.md").write_text("a bare `tool.invocation` message\n", encoding="utf-8")


def test_a_spend_of_the_name_a_site_declares_is_paid_by_that_site(tmp_path: Path) -> None:
    _hand(tmp_path, "_logger.info(_MESSAGE, extra=fields)")
    assert crosscheck.check_constant(tmp_path, HANDED) == []


def test_a_call_handed_another_word_leaves_the_call_mention_unfound(tmp_path: Path) -> None:
    _hand(tmp_path, '_logger.info("tool.dispatch", extra=fields)')
    (fault,) = crosscheck.check_constant(tmp_path, HANDED)
    assert "sink.py does not write '_logger.info(_MESSAGE,' as a token of its own" in fault.detail
    assert "does still write '_MESSAGE' as a token of its own, once on line 1" in fault.detail
    assert searchtexts.APART in fault.detail


def test_a_call_handed_another_binding_is_the_same_fault(tmp_path: Path) -> None:
    _hand(tmp_path, "_logger.info(_LOGGER_NAME, extra=fields)")
    (fault,) = crosscheck.check_constant(tmp_path, HANDED)
    assert "does not write '_logger.info(_MESSAGE,'" in fault.detail


def test_a_renamed_value_faults_the_restatement_and_leaves_the_call_found(tmp_path: Path) -> None:
    _hand(tmp_path, "_logger.info(_MESSAGE, extra=fields)")
    (tmp_path / "sink.py").write_text(
        '_MESSAGE = "tool.dispatch"\n_logger.info(_MESSAGE, extra=fields)\n', encoding="utf-8"
    )
    (fault,) = crosscheck.check_constant(tmp_path, HANDED)
    assert fault.detail.startswith("runbook.md does not write")


DEADLINE = crosscheck.Constant(
    label="a shipped deadline",
    why="the stack substitutes the default the adapter declares",
    sites=(crosscheck.Site("gateway.py", "DEFAULT_CALL_TIMEOUT_S"),),
    mentions=(crosscheck.Mention("stack.yml", "${CORTEX_BODY_CALL_TIMEOUT_S:-{value}}"),),
)


def _deadline(root: Path, declared: str, substituted: str) -> None:
    """Write a timeout declared in an adapter and repeated as a compose substitution default."""
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
    _deadline(tmp_path, declared="7.5", substituted="5.0")
    (fault,) = crosscheck.check_constant(tmp_path, DEADLINE)
    assert "does not write '${CORTEX_BODY_CALL_TIMEOUT_S:-7.5}'" in fault.detail


def test_the_same_number_without_its_point_is_a_different_form(tmp_path: Path) -> None:
    _deadline(tmp_path, declared="5", substituted="5.0")
    (fault,) = crosscheck.check_constant(tmp_path, DEADLINE)
    assert "does not write '${CORTEX_BODY_CALL_TIMEOUT_S:-5}'" in fault.detail


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
    _both_declare(tmp_path, rust="2.5", python="2.50")
    (fault,) = crosscheck.check_constant(tmp_path, DECIMAL_PAIR)
    assert "not identical" in fault.detail
    assert "body.rs: LEASE_S = 2.5," in fault.detail
    assert "brain.py: LEASE_S = 2.50" in fault.detail


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
            form=couplings.Form.WHOLE,
        ),
    ),
)


def _budget(root: Path, declared: str, passed: str, limit: str) -> None:
    """Write a memory budget passed to a process and repeated as a docker memory limit."""
    (root / "config.py").write_text(f"DEFAULT_MEM_BUDGET_GB = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      BUDGET_GB: "${{BUDGET_GB:-{passed}}}"\n'
        f'    mem_limit: "${{BUDGET_GB:-{limit}}}g"\n'
        f'    memswap_limit: "${{BUDGET_GB:-{limit}}}g"\n',
        encoding="utf-8",
    )


def test_one_number_ties_the_far_side_that_cannot_write_it_as_written(tmp_path: Path) -> None:
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    assert crosscheck.check_constant(tmp_path, BUDGET) == []


def test_retuning_the_budget_alone_fails_both_forms(tmp_path: Path) -> None:
    _budget(tmp_path, declared="12.0", passed="8.0", limit="8")
    written, whole = crosscheck.check_constant(tmp_path, BUDGET)
    assert "does not write '\"${BUDGET_GB:-12.0}\"'" in written.detail
    assert "does not write '\"${BUDGET_GB:-12}g\"' as a token of its own" in whole.detail
    assert "the registry sets 2 occurrences" in whole.detail


def test_one_of_the_two_limits_moving_alone_is_a_count_short(tmp_path: Path) -> None:
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    stack = tmp_path / "stack.yml"
    stack.write_text(
        stack.read_text(encoding="utf-8").replace(':-8}g"\n    memswap', ':-9}g"\n    memswap'),
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "found 1 (on line 3), set to 2" in fault.detail


def test_a_site_that_drops_its_point_is_still_caught(tmp_path: Path) -> None:
    _budget(tmp_path, declared="8", passed="8.0", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "does not write '\"${BUDGET_GB:-8}\"'" in fault.detail


def test_a_budget_the_far_side_cannot_write_at_all_is_reported(tmp_path: Path) -> None:
    _budget(tmp_path, declared="8.5", passed="8.5", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, BUDGET)
    assert "8.5 cannot be written whole" in fault.detail


def test_an_entry_that_rewrites_everywhere_is_refused(tmp_path: Path) -> None:
    blind = BUDGET._replace(mentions=BUDGET.mentions[1:])
    _budget(tmp_path, declared="8.0", passed="8.0", limit="8")
    (fault,) = crosscheck.check_constant(tmp_path, blind)
    assert "nothing holds the form the site writes" in fault.detail


HATCH = crosscheck.Constant(
    label="an escape hatch's shipped answer",
    why="a hatch that ships open is not a hatch",
    sites=(crosscheck.Site("config.py", "DEFAULT_TLS_INSECURE"),),
    mentions=(
        crosscheck.Mention(
            "stack.yml",
            "${TLS_INSECURE:-{value}}",
            form=couplings.Form.LOWERED,
        ),
    ),
)


def _hatch(root: Path, declared: str, substituted: str) -> None:
    """Write a boolean a settings module declares and the compose default repeating it in YAML."""
    (root / "config.py").write_text(f"DEFAULT_TLS_INSECURE = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      TLS_INSECURE: "${{TLS_INSECURE:-{substituted}}}"\n', encoding="utf-8"
    )


def test_a_boolean_reaches_the_far_side_that_writes_it_in_lower_case(tmp_path: Path) -> None:
    _hatch(tmp_path, declared="False", substituted="false")
    assert crosscheck.check_constant(tmp_path, HATCH) == []


def test_a_hatch_the_stack_opens_alone_is_reported(tmp_path: Path) -> None:
    _hatch(tmp_path, declared="False", substituted="true")
    (fault,) = crosscheck.check_constant(tmp_path, HATCH)
    assert "does not write '${TLS_INSECURE:-false}'" in fault.detail


def test_a_hatch_the_field_opens_alone_is_reported_too(tmp_path: Path) -> None:
    _hatch(tmp_path, declared="True", substituted="false")
    (fault,) = crosscheck.check_constant(tmp_path, HATCH)
    assert "does not write '${TLS_INSECURE:-true}'" in fault.detail


def test_a_boolean_a_far_side_writes_as_the_site_does_needs_no_form(tmp_path: Path) -> None:
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
    """Write a module-private sentinel and the compose default that repeats it, sign included."""
    (root / "config.py").write_text(f"_UNRESTRICTED = {declared}\n", encoding="utf-8")
    (root / "stack.yml").write_text(
        f'      BUDGET: "${{BUDGET:-{substituted}}}"\n', encoding="utf-8"
    )


def test_a_signed_default_renders_into_the_shape_a_stack_substitutes(tmp_path: Path) -> None:
    _sentinel(tmp_path, declared="-1", substituted="-1")
    assert crosscheck.check_constant(tmp_path, SENTINEL) == []


def test_a_sentinel_the_stack_bounds_alone_is_reported(tmp_path: Path) -> None:
    _sentinel(tmp_path, declared="-1", substituted="512")
    (fault,) = crosscheck.check_constant(tmp_path, SENTINEL)
    assert "does not write '${BUDGET:--1}'" in fault.detail


def test_a_sentinel_renamed_past_its_underscore_is_a_fault_and_not_a_skip(tmp_path: Path) -> None:
    _sentinel(tmp_path, declared="-1", substituted="-1")
    (tmp_path / "config.py").write_text("_UNBOUNDED = -1\n", encoding="utf-8")
    (fault,) = crosscheck.check_constant(tmp_path, SENTINEL)
    assert "config.py declares no _UNRESTRICTED" in fault.detail


def test_check_walks_the_whole_registry(tmp_path: Path) -> None:
    second = BYTE_CEILING._replace(label="another ceiling")
    faults = crosscheck.check(tmp_path, (BYTE_CEILING, second))
    labels = ["a ceiling", "a ceiling", "another ceiling", "another ceiling"]
    assert [fault.label for fault in faults] == labels


def test_the_repo_itself_is_tied() -> None:
    assert crosscheck.check(REPO_ROOT) == []


REASONING_OFF = "the subagent tier's reasoning-off budget"
FLAG_GATE = "scripts/subagentflags.py"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"

DECLARED = '_NO_REASONING_BUDGET = "0"'
REQUIRED = 'Flag("--reasoning-budget", "0")'

TRAIL_LOGGER = "the logger one recall-trail line is written through"
TRAIL_MESSAGE = "the message one recall-trail line is found by"
TRAIL_FIELD = "the field a recall-trail line names the candidates it dropped under"
TRAIL_READER = "scripts/trailwidth.py"
RECALL_SINK = "brain/packages/memory/src/cortex_memory/audit.py"
MEMORY_MODULE = "docs/modules/brain-memory.md"

SINK_LOGGER = '_LOGGER_NAME = "cortex.memory.recall"'
SINK_MESSAGE = '_logger.info("memory.recall"'
SINK_FIELD = '"dropped": ['

AUDIT_LOGGER = "the logger one tool-audit line is written through"
AUDIT_MESSAGE = "the message one tool-audit line is found by"
AUDIT_SINK = "brain/packages/tools/src/cortex_tools/audit.py"
LEVEL_SUITE = "brain/packages/orchestrator/tests/test_config_logging.py"

SINK_WORD = '_MESSAGE = "tool.invocation"'
HANDED_CALL = "_logger.info(_MESSAGE,"
ASSERTED_LINE = "INFO:cortex.tools.audit:tool.invocation tool=read"

AUDIT_SUITE = "brain/packages/tools/tests/test_audit.py"

ASSERTED_WORD = ':tool.invocation "'

DECLARED_UNDER = "the name a sink that named itself declares that name under"
LOGGER_GUARD = "scripts/tests/test_loggernames.py"
TOOLS_MODULE = "docs/modules/brain-tools.md"

GUARD_ASK = 'DECLARATION = "_LOGGER_NAME"'
SINK_DECLARATION = '_LOGGER_NAME = "'
CONTRACT_DECLARATION = "the module as `_LOGGER_NAME`"


def registered(label: str) -> couplings.Constant:
    """Return the one registry entry with this label."""
    found = [constant for constant in crosscheck.CONSTANTS if constant.label == label]
    assert len(found) == 1, f"the registry holds no single entry labelled {label!r}"
    return found[0]


def copied(root: Path, constant: couplings.Constant, edits: dict[str, tuple[str, str]]) -> None:
    """Copy every file ``constant`` refers to under ``root``, applying one edit per named file."""
    places = [site.path for site in constant.sites]
    places.extend(mention.path for mention in constant.mentions)
    for place in places:
        text = (REPO_ROOT / place).read_text(encoding="utf-8")
        if place in edits:
            was, now = edits[place]
            assert was in text, f"{place} no longer writes {was!r}, so this mutation edits nothing"
            text = text.replace(was, now, 1)
        target = root / place
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def rewritten(root: Path, place: str, was: str, now: str) -> None:
    """Replace every occurrence of ``was`` in one file `copied` has already written."""
    target = root / place
    assert target.exists(), f"the entry under test names no {place}, so there is nothing to edit"
    text = target.read_text(encoding="utf-8")
    assert was in text, f"{place} no longer writes {was!r}, so this mutation edits nothing"
    target.write_text(text.replace(was, now), encoding="utf-8")


def test_the_reasoning_off_budget_holds_over_the_files_it_names(tmp_path: Path) -> None:
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {})
    assert crosscheck.check_constant(tmp_path, constant) == []


def test_a_gate_requiring_a_budget_the_hosted_tier_does_not_ship_is_a_fault(tmp_path: Path) -> None:
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {FLAG_GATE: (REQUIRED, REQUIRED.replace('"0"', '"128"'))})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [REASONING_OFF]
    assert FLAG_GATE in faults[0].detail


def test_the_hosted_tier_retuned_on_its_own_is_the_same_fault_from_the_other_side(
    tmp_path: Path,
) -> None:
    constant = registered(REASONING_OFF)
    copied(tmp_path, constant, {MODELHOST_CONFIG: (DECLARED, DECLARED.replace('"0"', '"128"'))})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {REASONING_OFF}
    assert len(faults) == len(constant.mentions), faults


def test_the_budget_is_held_by_this_entry_and_not_by_a_neighbour(tmp_path: Path) -> None:
    pair = registered(REASONING_OFF)
    neighbours = tuple(
        constant for constant in crosscheck.CONSTANTS if constant.label != REASONING_OFF
    )
    for constant in neighbours:
        copied(tmp_path, constant, {})
    copied(tmp_path, pair, {FLAG_GATE: (REQUIRED, "")})
    assert crosscheck.check(tmp_path, neighbours) == []
    assert [fault.label for fault in crosscheck.check(tmp_path, (pair,))] == [REASONING_OFF]


def test_the_trail_search_texts_hold_over_the_files_they_name(tmp_path: Path) -> None:
    for label in (TRAIL_LOGGER, TRAIL_MESSAGE, TRAIL_FIELD):
        constant = registered(label)
        copied(tmp_path, constant, {})
        assert crosscheck.check_constant(tmp_path, constant) == []


def test_renaming_the_trails_logger_in_the_sink_fails_every_document_that_states_it(
    tmp_path: Path,
) -> None:
    constant = registered(TRAIL_LOGGER)
    renamed = SINK_LOGGER.replace("recall", "trail")
    copied(tmp_path, constant, {RECALL_SINK: (SINK_LOGGER, renamed)})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {TRAIL_LOGGER}
    assert {fault.detail.split()[0] for fault in faults} == {
        mention.path for mention in constant.mentions
    }


def test_a_document_that_stops_naming_the_trails_logger_is_a_fault(tmp_path: Path) -> None:
    constant = registered(TRAIL_LOGGER)
    reworded = ("`cortex.memory.recall` line per recall,", "line per recall,")
    copied(tmp_path, constant, {MEMORY_MODULE: reworded})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_LOGGER]
    assert MEMORY_MODULE in faults[0].detail


def test_the_trails_field_moving_in_the_sink_alone_is_a_fault(tmp_path: Path) -> None:
    constant = registered(TRAIL_FIELD)
    copied(tmp_path, constant, {RECALL_SINK: (SINK_FIELD, '"passed_over": [')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_FIELD]
    assert RECALL_SINK in faults[0].detail


def test_the_trails_message_moving_fails_though_the_line_still_contains_the_word(
    tmp_path: Path,
) -> None:
    constant = registered(TRAIL_MESSAGE)
    copied(tmp_path, constant, {RECALL_SINK: (SINK_MESSAGE, '_logger.info("memory.ranked"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [TRAIL_MESSAGE]
    doctored = (tmp_path / RECALL_SINK).read_text(encoding="utf-8")
    assert "memory.recall" in doctored, "the logger goes on writing the word that was renamed"


def test_the_reader_retuning_its_own_search_text_is_the_same_fault_from_the_other_side(
    tmp_path: Path,
) -> None:
    constant = registered(TRAIL_FIELD)
    copied(tmp_path, constant, {TRAIL_READER: ('TRAIL_FIELD = "dropped"', 'TRAIL_FIELD = "cut"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {TRAIL_FIELD}
    assert len(faults) == len(constant.mentions), faults


def test_the_trails_field_is_held_by_this_entry_and_not_by_a_neighbour(tmp_path: Path) -> None:
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


def test_the_audit_messages_search_texts_hold_over_the_files_they_name(tmp_path: Path) -> None:
    copied(tmp_path, registered(AUDIT_MESSAGE), {})
    assert crosscheck.check_constant(tmp_path, registered(AUDIT_MESSAGE)) == []


def test_renaming_the_audit_message_in_the_sink_alone_fails_every_place_restating_it(
    tmp_path: Path,
) -> None:
    constant = registered(AUDIT_MESSAGE)
    copied(tmp_path, constant, {AUDIT_SINK: (SINK_WORD, '_MESSAGE = "tool.dispatch"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {AUDIT_MESSAGE}
    assert {fault.detail.split()[0] for fault in faults} == {
        mention.path for mention in constant.mentions if crosscheck.PLACEHOLDER in mention.template
    }


def test_the_audit_sink_handing_another_word_fails_at_the_call(tmp_path: Path) -> None:
    constant = registered(AUDIT_MESSAGE)
    copied(tmp_path, constant, {AUDIT_SINK: (HANDED_CALL, HANDED_CALL.replace("_MESSAGE", '"x"'))})
    (fault,) = crosscheck.check_constant(tmp_path, constant)
    assert fault.detail.startswith(f"{AUDIT_SINK} does not write {HANDED_CALL!r}")


def test_the_suites_asserted_line_is_reported_against_the_word_that_moved(
    tmp_path: Path,
) -> None:
    logger, message = registered(AUDIT_LOGGER), registered(AUDIT_MESSAGE)
    moved = {LEVEL_SUITE: (ASSERTED_LINE, ASSERTED_LINE.replace("invocation", "dispatch"))}
    copied(tmp_path, logger, moved)
    copied(tmp_path, message, moved)
    assert crosscheck.check(tmp_path, (logger,)) == []
    faults = crosscheck.check(tmp_path, (message,))
    assert [fault.label for fault in faults] == [AUDIT_MESSAGE]
    assert LEVEL_SUITE in faults[0].detail


def test_the_audit_loggers_search_texts_hold_over_the_files_they_name(tmp_path: Path) -> None:
    constant = registered(AUDIT_LOGGER)
    copied(tmp_path, constant, {})
    assert crosscheck.check_constant(tmp_path, constant) == []


def test_the_declarations_search_texts_hold_over_the_files_they_name(tmp_path: Path) -> None:
    constant = registered(DECLARED_UNDER)
    copied(tmp_path, constant, {})
    assert crosscheck.check_constant(tmp_path, constant) == []


def test_a_guard_that_stops_asking_for_the_declaration_is_a_fault(tmp_path: Path) -> None:
    constant = registered(DECLARED_UNDER)
    copied(tmp_path, constant, {LOGGER_GUARD: (GUARD_ASK, 'DECLARATION = "_TRAIL_NAME"')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert {fault.label for fault in faults} == {DECLARED_UNDER}
    assert {fault.detail.split()[0] for fault in faults} == {
        mention.path for mention in constant.mentions
    }


def test_a_sink_that_renames_its_declaration_alone_is_a_fault(tmp_path: Path) -> None:
    constant = registered(DECLARED_UNDER)
    copied(tmp_path, constant, {AUDIT_SINK: (SINK_DECLARATION, '_TRAIL_NAME = "')})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [DECLARED_UNDER]
    assert AUDIT_SINK in faults[0].detail


def test_a_contract_naming_a_binding_its_sink_does_not_make_is_a_fault(tmp_path: Path) -> None:
    constant = registered(DECLARED_UNDER)
    moved = (CONTRACT_DECLARATION, "the module as `_TRAIL_NAME`")
    copied(tmp_path, constant, {MEMORY_MODULE: moved})
    faults = crosscheck.check_constant(tmp_path, constant)
    assert [fault.label for fault in faults] == [DECLARED_UNDER]
    assert MEMORY_MODULE in faults[0].detail


def test_an_audit_suite_asserting_another_word_before_its_fields_is_a_fault(
    tmp_path: Path,
) -> None:
    message, logger = registered(AUDIT_MESSAGE), registered(AUDIT_LOGGER)
    copied(tmp_path, message, {})
    copied(tmp_path, logger, {})
    rewritten(tmp_path, AUDIT_SUITE, ASSERTED_WORD, ':tool.dispatch "')
    doctored = (tmp_path / AUDIT_SUITE).read_text(encoding="utf-8")
    assert "tool.invocation ok=True" in doctored, "the forged payload keeps the word it writes"
    faults = crosscheck.check_constant(tmp_path, message)
    assert [fault.label for fault in faults] == [AUDIT_MESSAGE]
    assert AUDIT_SUITE in faults[0].detail
    assert crosscheck.check_constant(tmp_path, logger) == []


def _parts_on_disk() -> list[str]:
    """Return the registry's part files, read from the directory rather than from a list."""
    return sorted(
        path.stem
        for path in (REPO_ROOT / "scripts").glob("*couplings.py")
        if path.stem != "couplings"
    )


def _entries(part: str) -> tuple[couplings.Constant, ...]:
    """Return one part's tuple of entries, found by the naming convention every part follows."""
    name = part.removesuffix("couplings").upper() + "_COUPLINGS"
    module = import_module(part)
    assert hasattr(module, name), (
        f"{part}.py exports no {name}: a registry part is a `<subject>couplings.py` holding a "
        f"`<SUBJECT>_COUPLINGS` tuple, which is how this suite finds one on disk"
    )
    exported: tuple[couplings.Constant, ...] = getattr(module, name)
    return exported


def test_the_parts_on_disk_are_exactly_what_the_registry_reads() -> None:
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
    seen = Counter(constant.label for constant in crosscheck.CONSTANTS)
    repeated = sorted(label for label, count in seen.items() if count > 1)
    assert not repeated, f"the registry holds these labels more than once: {repeated}"


def test_no_two_couplings_declare_one_set_of_sites() -> None:
    written: dict[tuple[crosscheck.Site, ...], list[str]] = {}
    for constant in crosscheck.CONSTANTS:
        written.setdefault(constant.sites, []).append(constant.label)
    repeated = sorted(labels for labels in written.values() if len(labels) > 1)
    assert not repeated, f"these labels are written over one set of declaring sites: {repeated}"


def _narrower(one: couplings.Constant, other: couplings.Constant) -> bool:
    """Whether ``one`` checks a subset of what ``other`` checks, which makes it a duplicate."""
    return (
        one.relation is couplings.Relation.EQUAL
        and other.relation is couplings.Relation.EQUAL
        and one.sites != other.sites
        and set(one.sites) <= set(other.sites)
        and set(one.mentions) <= set(other.mentions)
    )


def test_no_coupling_is_a_narrower_copy_of_another() -> None:
    copies = sorted(
        f"{one.label!r} inside {other.label!r}"
        for one in crosscheck.CONSTANTS
        for other in crosscheck.CONSTANTS
        if _narrower(one, other)
    )
    assert not copies, f"these couplings check a subset of another entry's places: {copies}"


def test_registry_names_every_part_in_the_order_it_reads_them() -> None:
    named = re.findall(r"^- `(\w+)` ", registry.__doc__ or "", re.MULTILINE)
    assert named, "registry.py names no part, so nothing says what the registry is written in"
    position = {constant: index for index, constant in enumerate(crosscheck.CONSTANTS)}
    read_in_order = sorted(
        _parts_on_disk(), key=lambda part: position.get(_entries(part)[0], len(position))
    )
    assert named == read_in_order


def test_every_registered_site_is_in_a_language_the_scan_knows() -> None:
    suffixes = {Path(site.path).suffix for c in crosscheck.CONSTANTS for site in c.sites}
    assert suffixes <= set(crosscheck.DECLARATIONS)


def _boundary_side(place: str) -> tuple[str, str]:
    """Return which side a registered file is on: its language and its brain package."""
    parts = Path(place).parts
    package = parts[2] if parts[:2] == ("brain", "packages") and len(parts) > 2 else ""
    return Path(place).suffix, package


def test_every_registered_constant_spans_more_than_one_boundary_side() -> None:
    for constant in crosscheck.CONSTANTS:
        places = [site.path for site in constant.sites]
        places.extend(mention.path for mention in constant.mentions)
        assert len({_boundary_side(place) for place in places}) > 1, constant.label


def test_every_registered_mention_renders_something_the_registry_fills() -> None:
    for constant in crosscheck.CONSTANTS:
        for mention in constant.mentions:
            renders_name = crosscheck.NAME_PLACEHOLDER in mention.template
            assert crosscheck.PLACEHOLDER in mention.template or renders_name, constant.label
            assert renders_name == (mention.name is not None), constant.label


def test_the_registry_spends_at_least_one_rendered_name() -> None:
    named = [
        mention
        for constant in crosscheck.CONSTANTS
        for mention in constant.mentions
        if mention.name is not None
    ]
    assert named
    assert any(crosscheck.PLACEHOLDER not in mention.template for mention in named)


BRAIN_SOURCE = logcalls.BRAIN_PACKAGES.as_posix() + "/"

SINK = "brain/packages/tools/src/cortex_tools/audit.py"

HELD_AT_CALL = crosscheck.Constant(
    label="a message handed to its call",
    why="the runbook restates the word, and the call spends the binding by name",
    sites=(crosscheck.Site(SINK, "_MESSAGE"),),
    mentions=(
        crosscheck.Mention("docs/runbooks/tools.md", "a bare `{value}` message"),
        crosscheck.Mention(SINK, "_logger.info({name},", name="_MESSAGE"),
    ),
)


def handed_sites(
    root: Path, constants: tuple[couplings.Constant, ...]
) -> list[tuple[couplings.Constant, couplings.Site, list[int]]]:
    """Return every registry site passed to a brain log call as its message, with those lines."""
    found: list[tuple[couplings.Constant, couplings.Site, list[int]]] = []
    for constant in constants:
        for site in constant.sites:
            if Path(site.path).suffix != ".py" or not site.path.startswith(BRAIN_SOURCE):
                continue
            tree = logcalls.parsed(logcalls.read(root / site.path, site.path), site.path)
            lines = [line for line, name in logcalls.handed(tree) if name == site.name]
            if lines:
                found.append((constant, site, lines))
    return found


def covered_lines(root: Path, constant: couplings.Constant, site: couplings.Site) -> set[int]:
    """Return every line a mention of ``site``'s own name covers in the file declaring it."""
    text = (root / site.path).read_text(encoding="utf-8")
    value = crosscheck.read_value(root, site)
    lines: set[int] = set()
    for mention in constant.mentions:
        if mention.path != site.path or mention.name != site.name:
            continue
        for match in searchtexts.bounded(crosscheck.rendered(mention, value)).finditer(text):
            first = linereadings.line_of(text, match.start())
            last = linereadings.line_of(text, match.end() - 1)
            lines.update(range(first, last + 1))
    return lines


def _sink(root: Path, call: str) -> None:
    """Write a small tool audit whose log message is a constant above one call on line five."""
    path = root / SINK
    path.parent.mkdir(parents=True)
    path.write_text(f'_MESSAGE = "tool.invocation"\n\n\ndef note() -> None:\n    {call}\n', "utf-8")


def test_a_registered_binding_a_call_is_handed_is_read_with_the_line_handing_it(
    tmp_path: Path,
) -> None:
    _sink(tmp_path, "_logger.info(_MESSAGE, extra={})")
    (site,) = HELD_AT_CALL.sites
    assert handed_sites(tmp_path, (HELD_AT_CALL,)) == [(HELD_AT_CALL, site, [5])]


def test_a_registered_binding_no_call_is_handed_is_outside_the_set(tmp_path: Path) -> None:
    _sink(tmp_path, '_logger.info("tool.dispatch", extra={})')
    assert handed_sites(tmp_path, (HELD_AT_CALL,)) == []


def test_a_site_outside_the_brains_python_is_not_read(tmp_path: Path) -> None:
    elsewhere = crosscheck.Constant(
        label="elsewhere",
        why="two sides",
        sites=(
            crosscheck.Site("body/crates/core/src/lib.rs", "MAX"),
            crosscheck.Site("scripts/trailwidth.py", "TRAIL_MESSAGE"),
        ),
    )
    assert handed_sites(tmp_path, (elsewhere,)) == []


def test_a_call_mention_ends_up_on_the_line_handing_the_name(tmp_path: Path) -> None:
    _sink(tmp_path, "_logger.info(_MESSAGE, extra={})")
    assert covered_lines(tmp_path, HELD_AT_CALL, HELD_AT_CALL.sites[0]) == {5}


def test_a_mention_aimed_at_the_declaration_ends_up_there_and_not_on_the_call(
    tmp_path: Path,
) -> None:
    _sink(tmp_path, "_logger.info(_MESSAGE, extra={})")
    aimed = HELD_AT_CALL._replace(
        mentions=(crosscheck.Mention(SINK, '{name} = "', name="_MESSAGE"),)
    )
    assert covered_lines(tmp_path, aimed, aimed.sites[0]) == {1}


WRAPPED_CALL = "_logger.info(\n        _MESSAGE,\n        extra={},\n    )"


def test_a_call_mention_naming_the_call_ends_up_nowhere_on_a_wrapped_one(tmp_path: Path) -> None:
    _sink(tmp_path, WRAPPED_CALL)
    (site,) = HELD_AT_CALL.sites
    assert handed_sites(tmp_path, (HELD_AT_CALL,)) == [(HELD_AT_CALL, site, [6])]
    assert covered_lines(tmp_path, HELD_AT_CALL, site) == set()


def test_the_name_and_its_comma_are_covered_on_a_wrapped_call(tmp_path: Path) -> None:
    _sink(tmp_path, WRAPPED_CALL)
    shorter = HELD_AT_CALL._replace(
        mentions=(crosscheck.Mention(SINK, "{name},", name="_MESSAGE"),)
    )
    assert covered_lines(tmp_path, shorter, shorter.sites[0]) == {6}


def test_every_registered_binding_a_brain_log_call_is_handed_is_held_at_that_call() -> None:
    held = handed_sites(REPO_ROOT, crosscheck.CONSTANTS)
    assert held, "no registered binding is handed to a brain log call, so the fixtures are fiction"
    for constant, site, lines in held:
        missing = sorted(set(lines) - covered_lines(REPO_ROOT, constant, site))
        assert not missing, (
            f"{site.path} hands {site.name} to a log call on line(s) {missing} and the entry "
            f"{constant.label!r} has no mention on that line; add "
            f"Mention({site.path!r}, '<the call>({{name}},', name={site.name!r}) beside its "
            f"other mentions, so a call handed another word fails check-crosscheck. Where the "
            f"formatter wraps that call onto more than one line, the template naming the call is "
            f"found nowhere and '{{name}},' is the one that ends up on line(s) {missing}"
        )


WIDENINGS: list[tuple[str, Callable[[values.Value], bool]]] = [
    ("a decimal", lambda value: isinstance(value, values.Digits)),
    ("a boolean", lambda value: isinstance(value, values.Truth)),
    ("a signed integer", lambda value: isinstance(value, int) and value < 0),
]


@pytest.mark.parametrize(("form", "reads"), WIDENINGS)
def test_the_registry_reduces_every_form_the_reducer_was_widened_for(
    form: str, reads: Callable[[values.Value], bool]
) -> None:
    read = [
        crosscheck.read_value(REPO_ROOT, site)
        for constant in crosscheck.CONSTANTS
        for site in constant.sites
    ]
    assert any(reads(value) for value in read), form


def test_the_registry_exercises_every_form() -> None:
    written = {mention.form for constant in crosscheck.CONSTANTS for mention in constant.mentions}
    assert written == set(couplings.Form)


def test_the_registry_exercises_every_relation() -> None:
    assert {constant.relation for constant in crosscheck.CONSTANTS} == set(crosscheck.Relation)


def test_the_registry_holds_couplings_of_both_kinds() -> None:
    assert any(constant.mentions for constant in crosscheck.CONSTANTS)
    assert any(len(constant.sites) > 1 for constant in crosscheck.CONSTANTS)


def test_the_registry_holds_at_least_one_occurrence_count() -> None:
    counted = [
        mention.occurrences
        for constant in crosscheck.CONSTANTS
        for mention in constant.mentions
        if mention.occurrences is not None
    ]
    assert counted
    assert all(count >= crosscheck.MIN_OCCURRENCES for count in counted)


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
    assert registry.shape(_SHAPED) == registry.Shape(entries=3, sites=4, mentions=5, counted=2)


def test_shape_of_an_empty_registry_is_all_zeros() -> None:
    assert registry.shape(()) == registry.Shape(entries=0, sites=0, mentions=0, counted=0)


def test_shape_counts_a_held_count_once_and_not_its_occurrences() -> None:
    counted_constants = registry.shape(_SHAPED).counted
    assert counted_constants == 2
    assert counted_constants != sum(
        mention.occurrences or 0 for constant in _SHAPED for mention in constant.mentions
    )


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert crosscheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "crosscheck OK" in capsys.readouterr().out


def test_main_states_the_registrys_shape_on_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert crosscheck.main(["--root", str(REPO_ROOT)]) == 0
    size = registry.shape(crosscheck.CONSTANTS)
    out = capsys.readouterr().out
    assert f"{size.entries} cross-tree constant(s)" in out
    assert f"{size.sites} declaring site(s)" in out
    assert f"{size.mentions} mention(s)" in out
    assert f"{size.counted} of them held to a count" in out


def test_main_fails_closed_when_no_site_can_be_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert crosscheck.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "the screen-capture byte ceiling: cannot read" in captured.out
    assert "the gRPC token's metadata key: cannot read" in captured.out
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


_RUN = '(\n    "The refused "\n    "query was "\n)'


def test_read_value_reads_a_python_run_of_literals_as_one_string(tmp_path: Path) -> None:
    (tmp_path / "decl.py").write_text(
        f"# preamble\nSENTENCE = {_RUN}\nafter = 1\n", encoding="utf-8"
    )
    assert crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "SENTENCE")) == (
        "The refused query was "
    )


def test_a_run_may_open_with_a_comment_and_contain_comment_lines(tmp_path: Path) -> None:
    text = 'SENTENCE = (  # why\n    "a "  # noqa\n    # a note\n\n    "b"\n)\nafter = 1\n'
    (tmp_path / "decl.py").write_text(text, encoding="utf-8")
    assert crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "SENTENCE")) == "a b"


def test_a_run_ties_to_a_one_line_site_and_to_a_run_broken_elsewhere(tmp_path: Path) -> None:
    (tmp_path / "one.py").write_text('SENTENCE = "The refused query was "\n', encoding="utf-8")
    (tmp_path / "two.py").write_text(f"SENTENCE = {_RUN}\n", encoding="utf-8")
    (tmp_path / "three.py").write_text(
        'SENTENCE = (\n    "The "\n    "refused query "\n    "was "\n)\n', encoding="utf-8"
    )
    entry = crosscheck.Constant(
        label="a sentence",
        why="nothing",
        sites=tuple(crosscheck.Site(f"{n}.py", "SENTENCE") for n in ("one", "two", "three")),
    )
    assert crosscheck.check_constant(tmp_path, entry) == []


def test_one_word_moved_inside_a_run_is_a_fault_naming_both_readings(tmp_path: Path) -> None:
    (tmp_path / "one.py").write_text('SENTENCE = "The refused query was "\n', encoding="utf-8")
    (tmp_path / "two.py").write_text(
        'SENTENCE = (\n    "The rejected "\n    "query was "\n)\n', encoding="utf-8"
    )
    entry = crosscheck.Constant(
        label="a sentence",
        why="nothing",
        sites=(crosscheck.Site("one.py", "SENTENCE"), crosscheck.Site("two.py", "SENTENCE")),
    )
    (fault,) = crosscheck.check_constant(tmp_path, entry)
    assert "refused" in fault.detail
    assert "rejected" in fault.detail


def test_a_run_that_never_closes_falls_back_to_the_line_and_is_refused(tmp_path: Path) -> None:
    (tmp_path / "decl.py").write_text('SENTENCE = (\n    "a "\nafter = 1\n', encoding="utf-8")
    with pytest.raises(crosscheck.CrossCheckError, match="parenthesized run"):
        crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "SENTENCE"))


def test_a_run_ends_at_the_first_line_that_closes_it(tmp_path: Path) -> None:
    text = f'SENTENCE = {_RUN}\nOTHER = (\n    "x"\n)\n'
    (tmp_path / "decl.py").write_text(text, encoding="utf-8")
    assert crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "OTHER")) == "x"
    assert crosscheck.read_value(tmp_path, crosscheck.Site("decl.py", "SENTENCE")) == (
        "The refused query was "
    )
