"""Behavior tests for LoggingAuditSink: one structured log record per invocation."""

import logging
from datetime import UTC, datetime

import pytest

from cortex_core import ToolInvocation
from cortex_tools import LoggingAuditSink

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


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
    assert record.getMessage() == "tool.invocation"
    assert (fields["tool"], fields["ok"], fields["arguments"]) == (
        "read",
        True,
        {"path": "/etc/hosts"},
    )
    assert fields["result_chars"] == 100
    assert "error" not in fields  # success never logs the (large/sensitive) content


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
