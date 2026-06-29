"""Behavior tests for ToolDispatcher: run one call, and audit every outcome.

The dispatcher's contract is that no dispatch is ever unaudited and a failure never
crashes the loop. A registry error comes back as an ``is_error`` result the model reads.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

from cortex_core import (
    InMemoryToolRegistry,
    RecordingAuditSink,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolResult,
    ToolSpec,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    """Clock pinned to a single instant, so audit timestamps are assertable."""

    def now(self) -> datetime:
        return _AT


def _spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=name, parameters={"type": "object"})


async def _ran(arguments: Mapping[str, object]) -> str:
    return f"ran:{arguments['path']}"


async def _boom(arguments: Mapping[str, object]) -> str:
    del arguments
    msg = "tool blew up"
    raise ToolError(msg)


def _dispatcher(registry: InMemoryToolRegistry, sink: RecordingAuditSink) -> ToolDispatcher:
    return ToolDispatcher(registry, sink, _FixedClock())


async def test_successful_call_returns_the_result_and_audits_ok() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    result = await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c-1", name="read", arguments={"path": "/etc/hosts"})
    )
    assert result == ToolResult(call_id="c-1", content="ran:/etc/hosts", is_error=False)
    (record,) = sink.records
    assert (record.name, record.ok, record.detail, record.at) == (
        "read",
        True,
        "ran:/etc/hosts",
        _AT,
    )
    assert record.arguments == {"path": "/etc/hosts"}


async def test_unknown_tool_becomes_an_error_result_and_is_audited() -> None:
    sink = RecordingAuditSink()
    result = await _dispatcher(InMemoryToolRegistry({}), sink).dispatch(
        ToolCall(id="c-2", name="missing", arguments={})
    )
    assert result.call_id == "c-2"
    assert result.is_error is True
    assert "missing" in result.content
    (record,) = sink.records
    assert record.ok is False
    assert "missing" in record.detail


async def test_tool_failure_becomes_an_error_result_and_is_audited() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _boom)})
    result = await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c-3", name="read", arguments={})
    )
    assert result == ToolResult(call_id="c-3", content="tool blew up", is_error=True)
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, "tool blew up")


async def test_describe_tools_passes_through_to_the_registry() -> None:
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran), "list": (_spec("list"), _ran)})
    specs = await _dispatcher(registry, RecordingAuditSink()).describe_tools()
    assert [spec.name for spec in specs] == ["read", "list"]
