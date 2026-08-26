"""Behaviour of the reader that turns a documented log line back into what it claims to print.

The fixtures are miniatures of the three samples the runbooks really carry, written the way each
of those is written: one bare inside a `text` fence, one prefixed by compose's own container
label, one commented out inside a shell block and wrapped over two lines. A fixture inventing its
own spelling would test the reader against itself, so the last tests here read the committed
runbooks, where the shapes are true or this gate is worthless.
"""

from pathlib import Path

import logsamples

REPO_ROOT = Path(__file__).resolve().parents[2]

SETTLE_LINE = (
    'WARNING:cortex_core.swap_settle:a handoff ended failed reason="<what happened>" '
    "session_id=<chat id> turn_id=<turn id>"
)

BARE = f"Some prose about a stream.\n\n```text\n{SETTLE_LINE}\n```\n"

PREFIXED = """\
```text
brain-1  | INFO:cortex_orchestrator.server:seam server listening host=0.0.0.0 port=50051
```
"""

WRAPPED = """\
```bash
docker compose logs brain | grep "quarantining"
# ERROR:cortex_session.schedule_claims:quarantining a corrupt schedule record \\
#   dead_key=cortex:schedules:dead item_id=<id>
```
"""


def only(text: str) -> logsamples.Sample:
    """The one sample in ``text``, asserted to be one so a miscount cannot read as a pass."""
    found = logsamples.samples(text)
    assert len(found) == 1
    return found[0]


# ── what a sample says ─────────────────────────────────────────────────────────


def test_a_fenced_line_yields_its_level_logger_message_and_field_names() -> None:
    sample = only(BARE)
    assert sample.level == "WARNING"
    assert sample.logger == "cortex_core.swap_settle"
    assert sample.message == "a handoff ended failed"
    assert sample.fields == ("reason", "session_id", "turn_id")


def test_the_line_number_is_the_line_the_sample_opens_on() -> None:
    """A fault points a reader at the page, so the number is the sample's own line."""
    assert only(BARE).line == 4


def test_values_are_dropped_and_only_the_names_survive() -> None:
    """One runbook's captured port is a dated reading, so this reader must not carry values."""
    assert only(PREFIXED).fields == ("host", "port")


def test_a_container_label_in_front_of_the_line_is_decoration() -> None:
    """Compose prefixes every line it prints, and none of that prefix is the line."""
    assert only(PREFIXED).logger == "cortex_orchestrator.server"


def test_a_message_with_no_fields_reads_as_a_message_and_no_fields() -> None:
    sample = only("```text\nINFO:cortex_core.engine:the turn converged\n```\n")
    assert (sample.message, sample.fields) == ("the turn converged", ())


# ── where the message stops ────────────────────────────────────────────────────


def test_an_equals_inside_a_quoted_value_does_not_open_a_field() -> None:
    """The formatter quotes any value carrying a space, so an `=` inside one is that value's."""
    sample = only('```text\nINFO:cortex_core.engine:done reason="a=b happened" ok=True\n```\n')
    assert sample.fields == ("reason", "ok")


def test_a_quoted_candidate_before_the_first_real_field_is_stepped_over() -> None:
    """The message ends at the first field OUTSIDE a quote, not at the first candidate."""
    sample = only('```text\nINFO:cortex_core.engine:said " weird=thing " ok=True\n```\n')
    assert (sample.message, sample.fields) == ('said " weird=thing "', ("ok",))


# ── a sample that wraps ────────────────────────────────────────────────────────


def test_a_wrapped_sample_is_read_as_the_one_line_it_stands_for() -> None:
    sample = only(WRAPPED)
    assert sample.message == "quarantining a corrupt schedule record"
    assert sample.fields == ("dead_key", "item_id")


def test_the_comment_marker_on_a_continuation_is_dropped_rather_than_read() -> None:
    """Left in, it would sit between the message and the first field and lengthen the message."""
    assert "#" not in only(WRAPPED).message


def test_a_continuation_stops_at_the_fence_that_closes_the_block() -> None:
    """A backslash on a block's last line must not swallow the marker that ends the block."""
    text = "```text\nINFO:cortex_core.engine:done ok=True \\\n```\nprose ok=False\n"
    assert only(text).fields == ("ok",)


def test_a_continuation_stops_at_the_end_of_the_document() -> None:
    """The other end of the same guard: there is no next line to fold in."""
    assert only("```text\nINFO:cortex_core.engine:done ok=True \\").fields == ("ok",)


# ── what is not a sample ───────────────────────────────────────────────────────


def test_the_same_text_in_a_paragraph_is_prose_and_not_a_sample() -> None:
    """Reading prose would make every inline mention owe a field list."""
    assert logsamples.samples("Look for INFO:cortex_core.engine:the turn converged.\n") == []


def test_an_ordinary_fenced_line_is_not_mistaken_for_a_rendered_one() -> None:
    assert logsamples.samples("```bash\ndocker compose logs brain\n```\n") == []


def test_every_fenced_block_is_read_and_the_prose_between_them_is_not() -> None:
    assert len(logsamples.samples(BARE + "\nand then\n\n" + PREFIXED)) == 2


# ── the runbooks this reader is written for ────────────────────────────────────


def test_the_committed_runbooks_carry_the_three_shapes_the_fixtures_copy() -> None:
    """A guard on the fixtures: a shape nobody writes any more would test this against itself."""
    printed = {
        sample.logger: sample
        for runbook in sorted((REPO_ROOT / "docs" / "runbooks").glob("*.md"))
        for sample in logsamples.samples(runbook.read_text(encoding="utf-8"))
    }
    assert printed["cortex_core.swap_settle"].fields == ("reason", "session_id", "turn_id")
    assert printed["cortex_orchestrator.server"].fields == ("host", "port")
    assert printed["cortex_session.schedule_claims"].fields == ("dead_key", "item_id")
