"""Behavior tests for LoggingAuditSink: one structured log record per invocation."""

import json
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import ToolInvocation, Trust
from cortex_tools import LoggingAuditSink

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _payload(record: logging.LogRecord) -> dict[str, object]:
    """The JSON payload embedded in the message (what a plain formatter actually prints)."""
    prefix, _, payload = record.getMessage().partition(" ")
    assert prefix == "tool.invocation"
    return json.loads(payload)


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
    assert _payload(record) == {  # the message is self-contained under any handler
        "tool": "read",
        "ok": True,
        "arguments": {"path": "/etc/hosts"},
        "trust": "untrusted",
        "at": "2026-07-03T12:00:00+00:00",
        "result_chars": 100,
    }


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
    payload = _payload(record)
    assert payload["error"] == "permission denied"
    assert "result_chars" not in payload


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
    assert _payload(record)["trust"] == "trusted"
