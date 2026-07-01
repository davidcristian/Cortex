"""Behavior tests for ToolDispatcher: run one call, and audit every outcome.

The dispatcher's contract is that no dispatch is ever unaudited and a failure never
crashes the loop. A registry error comes back as an ``is_error`` result the model reads.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

from cortex_core import (
    DENIED_MSG,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolResult,
    ToolSpec,
    Trust,
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


def _outbound(sink: RecordingAuditSink, confirmer: RecordingConfirmer | None) -> ToolDispatcher:
    """A dispatcher over a spy 'send' tool that records whether it ran."""
    return ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        sink,
        _FixedClock(),
        confirmer=confirmer,
    )


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


async def test_tool_failure_becomes_a_trusted_error_result_and_is_audited() -> None:
    # A dispatch error is our own message, not external content (ADR-0013): trusted, so it
    # neither frames as data nor taints the turn.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _boom)})
    result = await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c-3", name="read", arguments={})
    )
    assert result == ToolResult(
        call_id="c-3", content="tool blew up", is_error=True, trust=Trust.TRUSTED
    )
    (record,) = sink.records
    assert (record.ok, record.detail, record.trust) == (False, "tool blew up", Trust.TRUSTED)


async def test_audit_records_the_result_provenance() -> None:
    # The in-memory registry is the remote (untrusted) twin, so its results are UNTRUSTED.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"})
    )
    (record,) = sink.records
    assert record.trust is Trust.UNTRUSTED


async def test_gated_tool_on_a_tainted_turn_is_blocked_without_a_confirmer() -> None:
    # Fail-closed: no confirmer wired -> the gated action is denied and never runs.
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}), tainted=True, gated=True
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG
    assert result.trust is Trust.TRUSTED  # the block is our own message, not external content
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, DENIED_MSG)


async def test_gated_tool_on_a_tainted_turn_runs_when_the_confirmer_approves() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}), tainted=True, gated=True
    )
    assert result.content == "ran:/p"  # the tool ran
    (request,) = confirmer.requests
    assert request.tool_name == "send"
    assert "untrusted" in request.reason


async def test_gated_tool_on_a_tainted_turn_is_blocked_when_the_confirmer_denies() -> None:
    confirmer = RecordingConfirmer(answer=False)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}), tainted=True, gated=True
    )
    assert result.content == DENIED_MSG
    assert confirmer.requests != ()  # it was asked, and said no


async def test_gated_tool_on_a_clean_turn_runs_without_confirmation() -> None:
    # No untrusted content in the turn -> no elevated risk -> the gate does not engage.
    confirmer = RecordingConfirmer(answer=False)  # would deny if it were asked
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}), tainted=False, gated=True
    )
    assert result.content == "ran:/p"
    assert confirmer.requests == ()  # never consulted


async def test_ungated_tool_on_a_tainted_turn_runs_without_confirmation() -> None:
    confirmer = RecordingConfirmer(answer=False)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}), tainted=True, gated=False
    )
    assert result.content == "ran:/p"
    assert confirmer.requests == ()


async def test_describe_tools_passes_through_to_the_registry() -> None:
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran), "list": (_spec("list"), _ran)})
    specs = await _dispatcher(registry, RecordingAuditSink()).describe_tools()
    assert [spec.name for spec in specs] == ["read", "list"]
