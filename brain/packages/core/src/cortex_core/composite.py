"""CompositeToolRegistry: merge built-in tools with a remote ToolRegistry (ADR-0010).

Built-in tools are pure-core handlers (e.g. ``spawn_subagents``) the cortex calls exactly like
any MCP tool. This registry advertises the union behind the unchanged ``ToolRegistry`` port and
routes each ``invoke`` by name. Built-ins take precedence: a remote tool sharing a built-in's
name is shadowed (neither advertised nor invoked) and duplicate built-in names are a
construction error. ADR-0001 Q2 calls this the internal-tool seam; the body's OS actions
register here too, alongside delegation.
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.errors import ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec


class BuiltinTool(Protocol):
    """A pure-core tool the ``CompositeToolRegistry`` advertises and invokes directly."""

    @property
    def spec(self) -> ToolSpec: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class CompositeToolRegistry:
    """A ``ToolRegistry`` advertising built-in tools plus an optional remote registry's tools."""

    def __init__(self, builtins: Sequence[BuiltinTool], remote: ToolRegistry | None = None) -> None:
        by_name: dict[str, BuiltinTool] = {}
        for tool in builtins:
            name = tool.spec.name
            if name in by_name:
                msg = f"duplicate built-in tool name {name!r}"
                raise ValueError(msg)
            by_name[name] = tool
        self._builtins = by_name
        self._remote = remote

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """Advertise every built-in, then the remote tools a built-in does not shadow."""
        specs = [tool.spec for tool in self._builtins.values()]
        if self._remote is not None:
            remote_specs = await self._remote.describe_tools()
            specs.extend(spec for spec in remote_specs if spec.name not in self._builtins)
        return tuple(specs)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Route to the named built-in, else the remote registry, else raise ToolNotFoundError."""
        builtin = self._builtins.get(call.name)
        if builtin is not None:
            return await builtin.invoke(call)
        if self._remote is not None:
            return await self._remote.invoke(call)
        msg = f"unknown tool {call.name!r}"
        raise ToolNotFoundError(msg)
