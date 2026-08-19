"""Behavior tests for LoggingAuditSink: one structured log record per invocation."""

import logging
from datetime import UTC, datetime

import pytest

from cortex_core import PlainFormatter, ToolInvocation, Trust
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
