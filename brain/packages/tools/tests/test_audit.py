"""Behavior tests for LoggingAuditSink: one structured log record per invocation."""

import logging
from datetime import UTC, datetime

import pytest

from cortex_core import CUT, VALUE_CHARS, PlainFormatter, ToolInvocation, Trust
from cortex_tools import LoggingAuditSink

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _line(record: logging.LogRecord) -> str:
    """The line an operator reads: the message, then the fields the entry's formatter renders.

    The sink used to serialize its own JSON copy into the message because the shipped handler
    printed nothing else. It no longer does, so what the trail is worth is now a property of the
    formatter, and these assertions are made against the rendered line rather than the record.
    """
    return PlainFormatter().format(record)


async def test_successful_invocation_logs_size_not_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read", arguments={"path": "/etc/hosts"}, ok=True, detail="x" * 100, at=_AT
        )
    )
    (record,) = caplog.records
    fields = record.__dict__
    assert (fields["tool"], fields["ok"], fields["arguments"]) == (
        "read",
        True,
        {"path": "/etc/hosts"},
    )
    assert fields["result_chars"] == 100
    assert fields["trust"] == "untrusted"  # the ADR-0013 provenance rides the durable trail
    assert "error" not in fields  # success never logs the (large/sensitive) content
    # The whole line, exactly: name order makes it deterministic, so this pins what an operator
    # sees rather than only what was attached.
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        'arguments={"path":"/etc/hosts"} at=2026-07-03T12:00:00+00:00 ok=True '
        "result_chars=100 tool=read trust=untrusted"
    )


async def test_failed_invocation_logs_the_error_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(name="read", arguments={}, ok=False, detail="permission denied", at=_AT)
    )
    (record,) = caplog.records
    fields = record.__dict__
    assert (fields["tool"], fields["ok"], fields["error"]) == ("read", False, "permission denied")
    assert "result_chars" not in fields
    line = _line(record)
    assert 'error="permission denied"' in line  # quoted, so the detail stays one field
    assert "result_chars" not in line


async def test_trusted_invocation_logs_its_trust_stamp(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="spawn", arguments={}, ok=True, detail="done", at=_AT, trust=Trust.TRUSTED
        )
    )
    (record,) = caplog.records
    assert record.__dict__["trust"] == "trusted"
    assert "trust=trusted" in _line(record)


async def test_the_line_names_the_work_the_call_was_made_for(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The join an operator makes (ADR-0009 named-work addendum), under the names it is made by.

    The three ids are printed under exactly the field names the rest of this repo's log lines
    spell them with, so grepping a failed turn's `turn_id` reaches the tool calls that preceded
    it and a delegated call names both its task and the turn that spawned it.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read",
            arguments={},
            ok=True,
            detail="hi",
            at=_AT,
            session_id="s-1",
            turn_id="t-1",
            task_id="st-1",
        )
    )
    (record,) = caplog.records
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 ok=True result_chars=2 session_id=s-1 "
        "task_id=st-1 tool=read trust=untrusted turn_id=t-1"
    )


async def test_an_unattributed_call_leaves_the_ids_off_the_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Absence, not an empty value: the ticker's own dispatch has no chat, turn or task, and
    a printed `turn_id=` would read as a value that went missing rather than as no such thing.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(name="read", arguments={}, ok=True, detail="hi", at=_AT)
    )
    (record,) = caplog.records
    fields = record.__dict__
    assert "session_id" not in fields
    assert "turn_id" not in fields
    assert "task_id" not in fields
    assert "call_id" not in fields  # a dispatch whose caller minted no id names none
    assert "item_id" not in fields
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 ok=True result_chars=2 tool=read "
        "trust=untrusted"
    )


async def test_a_turnless_caller_still_names_the_chat_it_fired_for(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The schedule ticker's shape: a fired item has the chat that scheduled it and no turn,
    so the line carries the one it has and stays silent about the one it does not.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="spawn_subagents",
            arguments={},
            ok=True,
            detail="done",
            at=_AT,
            session_id="chat-1",
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert "session_id=chat-1" in line
    assert "turn_id" not in line
    assert "task_id" not in line


async def test_the_line_names_the_call_it_records(caplog: pytest.LogCaptureFixture) -> None:
    """Which dispatch this line is (ADR-0009 named-call addendum), under the name the result
    and its `Role.TOOL` message are keyed by, so a turn's lines stop being interchangeable.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read", arguments={}, ok=True, detail="hi", at=_AT, call_id="call-7", turn_id="t"
        )
    )
    (record,) = caplog.records
    assert record.__dict__["call_id"] == "call-7"
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 call_id=call-7 ok=True result_chars=2 "
        "tool=read trust=untrusted turn_id=t"
    )


async def test_a_fired_item_is_named_beside_the_call_that_fired_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ticker's line: the item is its own field, off the stamp, and the call id that spells
    the same item is beside it, because one of the two is a string the brain minted and the
    other is only a string that happens to look like one.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="spawn_subagents",
            arguments={},
            ok=True,
            detail="done",
            at=_AT,
            call_id="schedule-t1",
            session_id="chat-1",
            item_id="t1",
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert "item_id=t1" in line
    assert "call_id=schedule-t1" in line
    assert "turn_id" not in line
    assert "task_id" not in line


async def test_a_model_authored_id_spelling_the_ticker_prefix_names_no_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The counterfeit the `schedule-` prefix invites, and why the item is not read out of it.

    A model can emit any call id it likes, this one included, and the line prints it as asked.
    What it cannot do is put `item_id` on the line, because that comes off the dispatch stamp
    the dispatcher overwrote. So the trail's statement that an item fired stays the brain's.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read",
            arguments={},
            ok=True,
            detail="hi",
            at=_AT,
            call_id="schedule-t1",
            session_id="chat-1",
            turn_id="t-1",
        )
    )
    (record,) = caplog.records
    assert "item_id" not in record.__dict__
    assert "item_id" not in _line(record)


async def test_a_hostile_id_cannot_forge_a_second_line(caplog: pytest.LogCaptureFixture) -> None:
    """The newline attack: an id built to end the line and open a plausible next one.

    The formatter quotes any rendering carrying whitespace, and quoting is `json.dumps`, so the
    newline arrives escaped and the forgery lands inside one value. One record, one line.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    forged = "c\nINFO:cortex.tools.audit:tool.invocation ok=True tool=send"
    await LoggingAuditSink().record(
        ToolInvocation(name="read", arguments={}, ok=True, detail="hi", at=_AT, call_id=forged)
    )
    (record,) = caplog.records
    line = _line(record)
    assert "\n" not in line
    assert line.count("tool.invocation") == 2  # the real message, and the forgery inside a value
    assert 'call_id="c\\nINFO:cortex.tools.audit:tool.invocation ok=True tool=send"' in line


async def test_a_hostile_id_cannot_counterfeit_another_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The quote attack: an id built to close its own value and open a field of its own.

    The quote is what forces quoting, so it comes back escaped and the whole forgery stays one
    field. The genuine `turn_id` is still the only one the line's own structure carries, which
    is the claim: a model chooses what is inside a value, never what the fields are.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read",
            arguments={},
            ok=True,
            detail="hi",
            at=_AT,
            call_id='c" turn_id=t-victim item_id=t1',
            turn_id="t-real",
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert 'call_id="c\\" turn_id=t-victim item_id=t1"' in line
    assert line.endswith(" turn_id=t-real")  # the real field, still last in name order
    assert record.__dict__["turn_id"] == "t-real"
    assert "item_id" not in record.__dict__


async def test_a_hostile_id_cannot_write_control_characters_into_the_stream(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A NUL, a carriage return and an ANSI escape all reach the line as escape sequences, so
    an id cannot repaint an operator's terminal or truncate what a reader sees.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read", arguments={}, ok=True, detail="hi", at=_AT, call_id="c\x00\r\x1b[31mred"
        )
    )
    (record,) = caplog.records
    line = _line(record)
    assert not any(character in line for character in "\x00\r\x1b")
    assert 'call_id="c\\u0000\\r\\u001b[31mred"' in line


async def test_an_over_long_id_is_cut_at_the_same_bound_every_value_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A megabyte of id costs the line what any other value would: `VALUE_CHARS` and a marker.

    An id with no whitespace would otherwise render bare, so this also pins that the bound is
    what forfeits bare rendering: the cut value is quoted, and the marker cannot be mistaken
    for text the id carried.
    """
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read", arguments={}, ok=True, detail="hi", at=_AT, call_id="c" * (VALUE_CHARS * 4)
        )
    )
    (record,) = caplog.records
    line = _line(record)
    rendered = line.split("call_id=", 1)[1].split(" ok=", 1)[0]
    assert rendered == '"' + "c" * (VALUE_CHARS - 1) + CUT.format(chars=VALUE_CHARS * 3 + 2)
    assert len(rendered) < VALUE_CHARS * 4
