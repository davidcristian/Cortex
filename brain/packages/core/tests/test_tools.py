"""Behavior tests for the tool value types and the in-memory ToolRegistry fake."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cortex_core import (
    ConfirmationRequest,
    InMemoryToolRegistry,
    Provenance,
    SourceKind,
    ToolCall,
    ToolInvocation,
    ToolNotFoundError,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.tool_budget import DispatchBudget

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


async def _noop(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


def _spec(name: str, description: str = "a tool") -> ToolSpec:
    return ToolSpec(name=name, description=description, parameters={"type": "object"})


def test_tool_result_defaults_to_success() -> None:
    assert ToolResult(call_id="c-1", content="hi").is_error is False


def test_tool_result_defaults_to_untrusted() -> None:
    # Fail-closed (ADR-0013): a result reaching the loop without a trust stamp is untrusted.
    assert ToolResult(call_id="c-1", content="hi").trust is Trust.UNTRUSTED


def test_tool_spec_defaults_to_ungated() -> None:
    assert _spec("read").gated is False


def test_tool_invocation_defaults_to_untrusted_provenance() -> None:
    assert ToolInvocation(name="read", arguments={}, ok=True, detail="x", at=_AT).trust is (
        Trust.UNTRUSTED
    )


def test_confirmation_request_carries_the_action_and_reason() -> None:
    request = ConfirmationRequest(tool_name="send_email", arguments={"to": "x"}, reason="outbound")
    assert (request.tool_name, request.arguments, request.reason) == (
        "send_email",
        {"to": "x"},
        "outbound",
    )


def test_tool_invocation_rejects_a_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ToolInvocation(
            name="read",
            arguments={},
            ok=True,
            detail="x",
            at=datetime(2026, 7, 3, 12, 0, 0),  # noqa: DTZ001 -- the naive value under test
        )


def test_tool_invocation_accepts_an_aware_timestamp() -> None:
    invocation = ToolInvocation(name="read", arguments={"p": 1}, ok=True, detail="x", at=_AT)
    assert invocation.at is _AT


async def test_registry_describe_tools_lists_specs_in_insertion_order() -> None:
    registry = InMemoryToolRegistry(
        {"read": (_spec("read"), _noop), "list": (_spec("list"), _noop)}
    )
    assert [spec.name for spec in await registry.describe_tools()] == ["read", "list"]


async def test_registry_describe_tools_is_empty_when_none_registered() -> None:
    assert list(await InMemoryToolRegistry({}).describe_tools()) == []


async def test_registry_invoke_runs_the_named_handler() -> None:
    registry = InMemoryToolRegistry({"read": (_spec("read"), _noop)})
    result = await registry.invoke(ToolCall(id="c", name="read", arguments={}))
    assert result == ToolResult(call_id="c", content="ok", is_error=False)


async def test_registry_invoke_raises_tool_not_found_for_an_unknown_tool() -> None:
    with pytest.raises(ToolNotFoundError, match="unknown tool 'missing'"):
        await InMemoryToolRegistry({}).invoke(ToolCall(id="c", name="missing", arguments={}))


def test_a_stamps_budget_is_carried_but_is_not_part_of_its_value() -> None:
    # The stamp stays a value even though the pool it carries is a live handle (ADR-0009
    # turn-wide addendum): two dispatches of one turn compare equal, and no caller can conclude
    # from equality that two turns share a pool. The handle itself is still reachable, since
    # that is the whole point of carrying it.
    pool = DispatchBudget(limit=4)
    stamped = TurnStamp(session_id="s", tainted=True, budget=pool)
    assert stamped == TurnStamp(session_id="s", tainted=True, budget=DispatchBudget(limit=9))
    assert stamped == TurnStamp(session_id="s", tainted=True)
    assert stamped != TurnStamp(session_id="other", tainted=True, budget=pool)
    assert stamped.budget is pool


def test_a_stamps_sources_are_part_of_its_value() -> None:
    # Provenance is a fact about the turn, not a live handle, so unlike the pool it is compared:
    # a stamp that has read a source is not the same stamp as one that has read none.
    source = Provenance(SourceKind.TOOL, "read_email")
    assert TurnStamp(tainted=True, sources=(source,)) != TurnStamp(tainted=True)
    assert TurnStamp(tainted=True, sources=(source,)) == TurnStamp(tainted=True, sources=(source,))
