"""Tests for the reader of the rendered lines a package's own suite asserts whole.

The fixtures are miniature suites: one assertion in each of the shapes a suite writes, of which
exactly one is read. The last tests read the committed tools package, whose audit suite is the
reason this reader exists, and hold it to asserting the shapes the tools runbook prints.
"""

from pathlib import Path

import pytest

import assertedlines
from logsamples import Sample

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_AUDIT = "brain/packages/tools/src/cortex_tools/audit.py"
TOOL_SUITE = "brain/packages/tools/tests"

# The shape the tool audit's suite really writes: the formatter's output on the left, the line
# split over two literals on the right, which the parser joins into one constant.
WHOLE = """\
def test_a_line() -> None:
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "ok=True tool=read"
    )
"""

LINE = Sample(
    line=3,
    level="INFO",
    logger="cortex.tools.audit",
    message="tool.invocation",
    fields=("ok", "tool"),
)


def suite(root: Path, files: dict[str, str]) -> Path:
    """Write a miniature package suite, each path relative to the package's tests directory."""
    for relative, text in files.items():
        path = root / TOOL_SUITE / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


# ── which suite ────────────────────────────────────────────────────────────────


def test_the_suite_stands_beside_the_source_directory_the_module_lives_under() -> None:
    assert assertedlines.suite_of(TOOL_AUDIT) == TOOL_SUITE


def test_a_module_under_no_source_directory_has_no_suite() -> None:
    with pytest.raises(assertedlines.AssertedLineError, match="not under a src directory"):
        assertedlines.suite_of("scripts/samplecheck.py")


# ── what one assertion renders ─────────────────────────────────────────────────


def test_an_equality_against_a_rendered_line_is_read_as_that_line() -> None:
    assert assertedlines.asserted(WHOLE, "t.py") == [LINE]


def test_the_line_may_stand_on_either_side_of_the_equality() -> None:
    swapped = (
        "def test_a_line() -> None:\n"
        '    assert "INFO:cortex.tools.audit:tool.invocation ok=True tool=read" == _line(record)\n'
    )
    assert assertedlines.asserted(swapped, "t.py") == [LINE._replace(line=2)]


def test_a_line_asserted_with_no_fields_reports_none() -> None:
    bare = (
        "def test_a_line() -> None:\n"
        '    assert _line(record) == "INFO:cortex.tools.audit:tool.invocation"\n'
    )
    assert assertedlines.asserted(bare, "t.py") == [LINE._replace(line=2, fields=())]


def test_a_containment_check_is_not_an_asserted_line() -> None:
    """A containment says the line carries this much, never that this is the line: the head
    checked here is a prefix of a longer line, and reading it whole would report a line with one
    field that the sink never prints."""
    head = (
        "def test_a_head() -> None:\n"
        '    assert "INFO:cortex.tools.audit:tool.invocation ok=True" in _line(record)\n'
    )
    assert assertedlines.asserted(head, "t.py") == []


def test_a_string_that_only_contains_the_prefix_is_not_a_line() -> None:
    """The match is anchored: what the formatter returned begins with the level."""
    inside = (
        "def test_a_head() -> None:\n"
        '    assert value == "c INFO:cortex.tools.audit:tool.invocation tool=send"\n'
    )
    assert assertedlines.asserted(inside, "t.py") == []


def test_a_string_carrying_a_newline_is_not_a_line_the_formatter_wrote() -> None:
    two = (
        "def test_two() -> None:\n"
        '    assert value == "INFO:cortex.tools.audit:tool.invocation ok=True\\ntool=read"\n'
    )
    assert assertedlines.asserted(two, "t.py") == []


@pytest.mark.parametrize(
    "statement",
    [
        'assert a == b == "INFO:cortex.tools.audit:tool.invocation ok=True"',
        'assert a != "INFO:cortex.tools.audit:tool.invocation ok=True"',
        'assert a < "INFO:cortex.tools.audit:tool.invocation ok=True"',
        "assert a == 12",
        'assert a == f"INFO:cortex.tools.audit:tool.invocation ok={ok}"',
        "assert a",
        "assert a == b",
    ],
)
def test_a_comparison_that_is_not_one_equality_against_a_string_is_left_unread(
    statement: str,
) -> None:
    assert assertedlines.asserted(f"def test_x() -> None:\n    {statement}\n", "t.py") == []


def test_a_suite_that_does_not_parse_is_a_fault() -> None:
    with pytest.raises(assertedlines.AssertedLineError, match=r"cannot parse t\.py"):
        assertedlines.asserted("def (:\n", "t.py")


# ── what a whole suite proves ──────────────────────────────────────────────────


def test_the_walk_reads_every_file_of_the_suite_in_a_fixed_order(tmp_path: Path) -> None:
    other = WHOLE.replace("ok=True tool=read", "ok=False tool=read")
    root = suite(tmp_path, {"test_b.py": WHOLE, "test_a.py": other})
    assert assertedlines.proven(root, TOOL_AUDIT) == [
        assertedlines.Proven(suite=f"{TOOL_SUITE}/test_a.py", sample=LINE),
        assertedlines.Proven(suite=f"{TOOL_SUITE}/test_b.py", sample=LINE),
    ]


def test_a_pruned_directory_under_the_suite_is_not_read(tmp_path: Path) -> None:
    root = suite(tmp_path, {"test_a.py": WHOLE, "__pycache__/test_stale.py": WHOLE})
    assert len(assertedlines.proven(root, TOOL_AUDIT)) == 1


def test_a_package_with_no_suite_is_a_fault(tmp_path: Path) -> None:
    with pytest.raises(assertedlines.AssertedLineError, match="is not a directory"):
        assertedlines.proven(tmp_path, TOOL_AUDIT)


def test_a_suite_file_that_is_not_text_is_a_fault(tmp_path: Path) -> None:
    root = suite(tmp_path, {"test_a.py": WHOLE})
    (root / TOOL_SUITE / "test_blob.py").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(assertedlines.AssertedLineError, match=r"cannot read .*test_blob\.py"):
        assertedlines.proven(root, TOOL_AUDIT)


def test_a_suite_file_that_does_not_parse_is_named(tmp_path: Path) -> None:
    root = suite(tmp_path, {"test_a.py": "def (:\n"})
    with pytest.raises(assertedlines.AssertedLineError, match=r"cannot parse .*test_a\.py"):
        assertedlines.proven(root, TOOL_AUDIT)


# ── the repo this reader reads ─────────────────────────────────────────────────


def test_the_real_audit_suite_asserts_every_shape_the_tools_runbook_prints() -> None:
    """The five field sets the runbook's fence carries, each asserted whole by the sink's suite.

    The timestamp is on every one of them, which is the field the runbook's prose enumeration had
    lost before the fence replaced it.
    """
    lines = assertedlines.proven(REPO_ROOT, TOOL_AUDIT)
    audited = {
        held.sample.fields
        for held in lines
        if (held.sample.logger, held.sample.message) == ("cortex.tools.audit", "tool.invocation")
    }
    assert {
        ("arguments", "at", "ok", "result_chars", "tool", "trust"),
        ("arguments", "at", "error", "ok", "tool", "trust"),
        (
            "arguments",
            "at",
            "call_id",
            "ok",
            "result_chars",
            "session_id",
            "tool",
            "trust",
            "turn_id",
        ),
        (
            "arguments",
            "at",
            "ok",
            "result_chars",
            "session_id",
            "task_id",
            "tool",
            "trust",
            "turn_id",
        ),
        (
            "arguments",
            "at",
            "call_id",
            "item_id",
            "ok",
            "result_chars",
            "session_id",
            "tool",
            "trust",
        ),
    } <= audited
    assert all("at" in fields for fields in audited)


def test_the_real_audit_suite_is_read_and_no_other_suite_is() -> None:
    """The orchestrator's logging suite asserts a one-field `cortex.tools.audit` line written
    straight through the logger, which the sink never prints; reading every brain suite would
    have held a runbook sample to it."""
    lines = assertedlines.proven(REPO_ROOT, TOOL_AUDIT)
    assert lines
    assert all(held.suite.startswith(f"{TOOL_SUITE}/") for held in lines)
    assert ("tool",) not in {held.sample.fields for held in lines}
