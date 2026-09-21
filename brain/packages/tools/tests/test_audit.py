import logging
from datetime import UTC, datetime

import pytest

from cortex_core import CUT, VALUE_CHARS, PlainFormatter, ToolInvocation, Trust
from cortex_tools import LoggingAuditSink

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _line(record: logging.LogRecord) -> str:
    """The line an operator reads: the message, then the fields the entry's formatter renders."""
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
    assert fields["trust"] == "untrusted"
    assert "error" not in fields
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
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        'arguments={} at=2026-07-03T12:00:00+00:00 error="permission denied" ok=False '
        "tool=read trust=untrusted"
    )


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
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(name="read", arguments={}, ok=True, detail="hi", at=_AT)
    )
    (record,) = caplog.records
    fields = record.__dict__
    assert "session_id" not in fields
    assert "turn_id" not in fields
    assert "task_id" not in fields
    assert "call_id" not in fields
    assert "item_id" not in fields
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 ok=True result_chars=2 tool=read "
        "trust=untrusted"
    )


async def test_a_turnless_caller_still_names_the_chat_it_fired_for(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    await LoggingAuditSink().record(
        ToolInvocation(
            name="read",
            arguments={},
            ok=True,
            detail="hi",
            at=_AT,
            call_id="call-7",
            session_id="s-1",
            turn_id="t",
        )
    )
    (record,) = caplog.records
    assert record.__dict__["call_id"] == "call-7"
    assert _line(record) == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 call_id=call-7 ok=True result_chars=2 "
        "session_id=s-1 tool=read trust=untrusted turn_id=t"
    )


async def test_a_fired_item_is_named_beside_the_call_that_fired_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    assert "turn_id" not in line
    assert "task_id" not in line
    assert line == (
        "INFO:cortex.tools.audit:tool.invocation "
        "arguments={} at=2026-07-03T12:00:00+00:00 call_id=schedule-t1 item_id=t1 ok=True "
        "result_chars=4 session_id=chat-1 tool=spawn_subagents trust=untrusted"
    )


async def test_a_model_authored_id_written_with_the_ticker_prefix_names_no_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    caplog.set_level(logging.INFO, logger="cortex.tools.audit")
    forged = "c\nINFO:cortex.tools.audit:tool.invocation ok=True tool=send"
    await LoggingAuditSink().record(
        ToolInvocation(name="read", arguments={}, ok=True, detail="hi", at=_AT, call_id=forged)
    )
    (record,) = caplog.records
    line = _line(record)
    assert "\n" not in line
    assert line.count("tool.invocation") == 2
    assert 'call_id="c\\nINFO:cortex.tools.audit:tool.invocation ok=True tool=send"' in line


async def test_a_hostile_id_cannot_counterfeit_another_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    assert line.endswith(" turn_id=t-real")
    assert record.__dict__["turn_id"] == "t-real"
    assert "item_id" not in record.__dict__


async def test_a_hostile_id_cannot_write_control_characters_into_the_stream(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
