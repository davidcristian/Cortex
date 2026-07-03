"""Behavior tests for the ToolRegistry combinators (ADR-0009 refinements addendum)."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import pytest

from cortex_core import (
    AggregateToolRegistry,
    FilteredToolRegistry,
    InMemoryToolRegistry,
    ToolCall,
    ToolError,
    ToolNotFoundError,
    ToolResult,
    ToolSpec,
)


def _replies(name: str) -> Callable[[Mapping[str, Any]], Awaitable[str]]:
    async def handler(arguments: Mapping[str, Any]) -> str:
        del arguments
        return f"from {name}"

    return handler


def _registry(label: str, *names: str) -> InMemoryToolRegistry:
    return InMemoryToolRegistry(
        {n: (ToolSpec(name=n, description="", parameters={}), _replies(label)) for n in names}
    )


class FailingRegistry:
    """A ToolRegistry whose listing always fails (the dead-sidecar case)."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        msg = "listing MCP tools failed"
        raise ToolError(msg)

    async def invoke(self, call: ToolCall) -> ToolResult:
        del call
        msg = "never routed to"
        raise ToolError(msg)


def test_aggregate_requires_at_least_one_registry() -> None:
    with pytest.raises(ValueError, match="at least one registry"):
        AggregateToolRegistry([])


async def test_describe_unions_in_registry_order() -> None:
    aggregate = AggregateToolRegistry([_registry("fs", "read", "list"), _registry("mail", "send")])
    names = [spec.name for spec in await aggregate.describe_tools()]
    assert names == ["read", "list", "send"]


async def test_describe_dedups_first_wins() -> None:
    first = _registry("fs", "read")
    shadowed = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="shadowed", parameters={}), _replies("mail"))}
    )
    aggregate = AggregateToolRegistry([first, shadowed])
    specs = await aggregate.describe_tools()
    assert len(specs) == 1
    assert specs[0].description == ""  # the first registry's spec, not the shadowed one


async def test_invoke_routes_to_the_advertising_registry() -> None:
    aggregate = AggregateToolRegistry([_registry("fs", "read"), _registry("mail", "send")])
    result = await aggregate.invoke(ToolCall(id="c1", name="send", arguments={}))
    assert result.content == "from mail"


async def test_invoke_routes_a_duplicate_name_to_the_first_registry() -> None:
    aggregate = AggregateToolRegistry([_registry("fs", "read"), _registry("mail", "read")])
    result = await aggregate.invoke(ToolCall(id="c2", name="read", arguments={}))
    assert result.content == "from fs"


async def test_invoke_unknown_everywhere_raises_not_found() -> None:
    aggregate = AggregateToolRegistry([_registry("fs", "read")])
    with pytest.raises(ToolNotFoundError, match="unknown tool 'nope'"):
        await aggregate.invoke(ToolCall(id="c3", name="nope", arguments={}))


async def test_a_dead_registry_fails_describe_loudly() -> None:
    aggregate = AggregateToolRegistry([_registry("fs", "read"), FailingRegistry()])
    with pytest.raises(ToolError, match="listing MCP tools failed"):
        await aggregate.describe_tools()


async def test_a_dead_registry_fails_invoke_routing_loudly() -> None:
    # The dead sidecar is walked before the user is found. The failure propagates.
    aggregate = AggregateToolRegistry([FailingRegistry(), _registry("mail", "send")])
    with pytest.raises(ToolError, match="listing MCP tools failed"):
        await aggregate.invoke(ToolCall(id="c4", name="send", arguments={}))


def test_filter_requires_a_non_empty_allowlist() -> None:
    with pytest.raises(ValueError, match="non-empty allowlist"):
        FilteredToolRegistry(_registry("fs", "read"), allow=[])


async def test_filter_advertises_only_allowlisted_tools() -> None:
    inner = _registry("fs", "read", "write", "list")
    filtered = FilteredToolRegistry(inner, allow=["read", "list"])
    names = [spec.name for spec in await filtered.describe_tools()]
    assert names == ["read", "list"]


async def test_filter_delegates_an_allowlisted_call() -> None:
    filtered = FilteredToolRegistry(_registry("fs", "read", "write"), allow=["read"])
    result = await filtered.invoke(ToolCall(id="c5", name="read", arguments={}))
    assert result.content == "from fs"


async def test_filter_refuses_a_call_outside_the_allowlist() -> None:
    # The inner registry HAS the tool; the filter is a real layer, not advisory.
    filtered = FilteredToolRegistry(_registry("fs", "read", "write"), allow=["read"])
    with pytest.raises(ToolNotFoundError, match="unknown tool 'write'"):
        await filtered.invoke(ToolCall(id="c6", name="write", arguments={}))


async def test_filter_only_restricts_never_grants() -> None:
    # An allowlisted name the inner registry lacks: unadvertised, and the inner not-found surfaces.
    filtered = FilteredToolRegistry(_registry("fs", "read"), allow=["read", "ghost"])
    assert [spec.name for spec in await filtered.describe_tools()] == ["read"]
    with pytest.raises(ToolNotFoundError, match="unknown tool 'ghost'"):
        await filtered.invoke(ToolCall(id="c7", name="ghost", arguments={}))
