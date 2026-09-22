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
brain-1  | INFO:cortex_orchestrator.server:gRPC server listening host=0.0.0.0 port=50051
```
"""

WRAPPED = """\
```bash
docker compose logs brain | grep "quarantining"
# ERROR:cortex_session.schedule_claims:quarantining a corrupt schedule record \\
#   dead_key=cortex:schedules:dead item_id=<id>
```
"""


NESTED = f"````markdown\n```text\n{SETTLE_LINE}\n```\n````\n"


def only(text: str) -> logsamples.Sample:
    """Return the one sample in ``text``, asserting the count so a miscount fails here."""
    found = logsamples.samples(text)
    assert len(found) == 1
    return found[0]


def test_a_fenced_line_yields_its_level_logger_message_and_field_names() -> None:
    sample = only(BARE)
    assert sample.level == "WARNING"
    assert sample.logger == "cortex_core.swap_settle"
    assert sample.message == "a handoff ended failed"
    assert sample.fields == ("reason", "session_id", "turn_id")


def test_the_line_number_is_the_line_the_sample_opens_on() -> None:
    assert only(BARE).line == 4


def test_values_are_dropped_and_only_the_names_survive() -> None:
    assert only(PREFIXED).fields == ("host", "port")


def test_a_container_label_in_front_of_the_line_is_decoration() -> None:
    assert only(PREFIXED).logger == "cortex_orchestrator.server"


def test_a_message_with_no_fields_reads_as_a_message_and_no_fields() -> None:
    sample = only("```text\nINFO:cortex_core.engine:the turn converged\n```\n")
    assert (sample.message, sample.fields) == ("the turn converged", ())


def test_an_equals_inside_a_quoted_value_does_not_open_a_field() -> None:
    sample = only('```text\nINFO:cortex_core.engine:done reason="a=b happened" ok=True\n```\n')
    assert sample.fields == ("reason", "ok")


def test_a_quoted_candidate_before_the_first_real_field_is_stepped_over() -> None:
    sample = only('```text\nINFO:cortex_core.engine:said " weird=thing " ok=True\n```\n')
    assert (sample.message, sample.fields) == ('said " weird=thing "', ("ok",))


def test_a_wrapped_sample_is_read_as_the_one_line_it_stands_for() -> None:
    sample = only(WRAPPED)
    assert sample.message == "quarantining a corrupt schedule record"
    assert sample.fields == ("dead_key", "item_id")


def test_the_comment_marker_on_a_continuation_is_dropped_rather_than_read() -> None:
    assert "#" not in only(WRAPPED).message


def test_a_continuation_stops_at_the_fence_that_closes_the_block() -> None:
    text = "```text\nINFO:cortex_core.engine:done ok=True \\\n```\nprose ok=False\n"
    assert only(text).fields == ("ok",)


def test_a_continuation_stops_at_the_end_of_the_document() -> None:
    assert only("```text\nINFO:cortex_core.engine:done ok=True \\").fields == ("ok",)


def test_the_same_text_in_a_paragraph_is_prose_and_not_a_sample() -> None:
    assert logsamples.samples("Look for INFO:cortex_core.engine:the turn converged.\n") == []


def test_a_block_written_with_the_other_marker_is_read_like_any_other() -> None:
    assert only(BARE.replace("```", "~~~")).logger == "cortex_core.swap_settle"


def test_an_ordinary_fenced_line_is_not_mistaken_for_a_rendered_one() -> None:
    assert logsamples.samples("```bash\ndocker compose logs brain\n```\n") == []


def test_every_fenced_block_is_read_and_the_prose_between_them_is_not() -> None:
    assert len(logsamples.samples(BARE + "\nand then\n\n" + PREFIXED)) == 2


def test_a_sample_inside_a_block_that_prints_a_fence_is_still_read() -> None:
    assert only(NESTED).logger == "cortex_core.swap_settle"


def test_a_line_continued_onto_a_marker_that_closes_nothing_folds_it_in() -> None:
    text = "````\nINFO:cortex_core.engine:done ok=True \\\n``` more=here\n````\n"
    assert only(text).fields == ("ok", "more")


def test_the_committed_runbooks_carry_the_three_shapes_the_fixtures_copy() -> None:
    printed = {
        sample.logger: sample
        for runbook in sorted((REPO_ROOT / "docs" / "runbooks").glob("*.md"))
        for sample in logsamples.samples(runbook.read_text(encoding="utf-8"))
    }
    assert printed["cortex_core.swap_settle"].fields == ("reason", "session_id", "turn_id")
    assert printed["cortex_orchestrator.server"].fields == ("host", "port")
    assert printed["cortex_session.schedule_claims"].fields == ("dead_key", "item_id")
