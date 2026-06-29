"""Behavior tests for CompositeToolRegistry: merge built-in and remote tools (ADR-0010)."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import pytest

from cortex_core import (
    CompositeToolRegistry,
    InMemoryToolRegistry,
    ToolCall,
    ToolNotFoundError,
    ToolResult,
    ToolSpec,
)


class FakeBuiltin:
    """A minimal BuiltinTool: one spec, a canned reply recording the call it saw."""

    def __init__(self, name: str, reply: str) -> None:
        self._name = name
        self._reply = reply
        self.seen: list[ToolCall] = []

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(name=self._name, description="", parameters={})

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.seen.append(call)
        return ToolResult(call_id=call.id, content=self._reply)


def _replies(name: str) -> Callable[[Mapping[str, Any]], Awaitable[str]]:
    async def handler(arguments: Mapping[str, Any]) -> str:
        del arguments
        return f"remote {name}"

    return handler


def _remote(*names: str) -> InMemoryToolRegistry:
    return InMemoryToolRegistry(
        {n: (ToolSpec(name=n, description="", parameters={}), _replies(n)) for n in names}
    )


def test_duplicate_builtin_names_are_a_construction_error() -> None:
    with pytest.raises(ValueError, match="duplicate built-in tool name"):
        CompositeToolRegistry([FakeBuiltin("dup", "a"), FakeBuiltin("dup", "b")])


async def test_describe_merges_builtins_then_unshadowed_remote_tools() -> None:
    registry = CompositeToolRegistry([FakeBuiltin("spawn", "x")], _remote("read", "spawn"))
    names = [spec.name for spec in await registry.describe_tools()]
    # Built-in first; the remote "spawn" is shadowed and not advertised twice.
    assert names == ["spawn", "read"]


async def test_describe_with_no_remote_lists_only_builtins() -> None:
    registry = CompositeToolRegistry([FakeBuiltin("spawn", "x")])
    assert [spec.name for spec in await registry.describe_tools()] == ["spawn"]


async def test_invoke_routes_to_the_builtin() -> None:
    builtin = FakeBuiltin("spawn", "spawned")
    registry = CompositeToolRegistry([builtin], _remote("read"))
    result = await registry.invoke(ToolCall(id="c1", name="spawn", arguments={}))
    assert result.content == "spawned"
    assert builtin.seen[0].id == "c1"


async def test_invoke_falls_through_to_the_remote() -> None:
    registry = CompositeToolRegistry([FakeBuiltin("spawn", "x")], _remote("read"))
    result = await registry.invoke(ToolCall(id="c2", name="read", arguments={}))
    assert result.content == "remote read"


async def test_invoke_unknown_without_a_remote_raises() -> None:
    registry = CompositeToolRegistry([FakeBuiltin("spawn", "x")])
    with pytest.raises(ToolNotFoundError, match="unknown tool 'nope'"):
        await registry.invoke(ToolCall(id="c3", name="nope", arguments={}))
