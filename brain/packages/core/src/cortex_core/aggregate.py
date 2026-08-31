"""Wrappers that combine or restrict a ``ToolRegistry`` and keep the same port."""

from collections.abc import Callable, Sequence
from dataclasses import replace

from cortex_core.errors import ToolError, ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec


class AggregateToolRegistry:
    """A ``ToolRegistry`` over several registries, routing each call by tool name."""

    def __init__(self, registries: Sequence[ToolRegistry]) -> None:
        if not registries:
            msg = "AggregateToolRegistry needs at least one registry"
            raise ValueError(msg)
        self._registries = tuple(registries)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The union of every registry's tools, deduplicated first-wins in registry order."""
        specs: dict[str, ToolSpec] = {}
        for registry in self._registries:
            for spec in await registry.describe_tools():
                if spec.name not in specs:
                    specs[spec.name] = spec
        return tuple(specs.values())

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Route to the first registry currently advertising ``call.name``."""
        for registry in self._registries:
            names = {spec.name for spec in await registry.describe_tools()}
            if call.name in names:
                return await registry.invoke(call)
        msg = f"unknown tool {call.name!r}"
        raise ToolNotFoundError(msg)


class SkipUnavailableToolRegistry:
    """A ``ToolRegistry`` that reports a failing inner registry and lists none of its tools."""

    def __init__(
        self, inner: ToolRegistry, *, name: str, report: Callable[[str, ToolError], None]
    ) -> None:
        self._inner = inner
        self._name = name
        self._report = report

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, or an empty (reported) advertisement when it fails."""
        try:
            return await self._inner.describe_tools()
        except ToolError as err:
            self._report(self._name, err)
            return ()

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Call the inner registry unchanged: only tool discovery handles a failure."""
        return await self._inner.invoke(call)


class UngatedToolRegistry:
    """A ``ToolRegistry`` with every tool that needs confirmation removed, for a subagent."""

    def __init__(self, inner: ToolRegistry) -> None:
        self._inner = inner

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools that need no confirmation, inner order kept."""
        return tuple(spec for spec in await self._inner.describe_tools() if not spec.gated)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Call a tool that needs no confirmation; any other name raises ``ToolNotFoundError``."""
        gated = {spec.name for spec in await self._inner.describe_tools() if spec.gated}
        if call.name in gated:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)


class GatedToolRegistry:
    """A ``ToolRegistry`` that advertises the named tools with ``gated`` set."""

    def __init__(self, inner: ToolRegistry, *, gated: Sequence[str]) -> None:
        if not gated:
            msg = "GatedToolRegistry needs a non-empty gated-name set"
            raise ValueError(msg)
        self._inner = inner
        self._gated = frozenset(gated)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, the named ones marked ``gated``, inner order kept."""
        return tuple(
            replace(spec, gated=True) if spec.name in self._gated else spec
            for spec in await self._inner.describe_tools()
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Call the inner registry unchanged; the dispatcher asks for the confirmation."""
        return await self._inner.invoke(call)


class FilteredToolRegistry:
    """A ``ToolRegistry`` restricted to an allowlist of tool names."""

    def __init__(self, inner: ToolRegistry, *, allow: Sequence[str]) -> None:
        if not allow:
            msg = "FilteredToolRegistry needs a non-empty allowlist"
            raise ValueError(msg)
        self._inner = inner
        self._allow = frozenset(allow)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools intersected with the allowlist, inner order kept."""
        specs = await self._inner.describe_tools()
        return tuple(spec for spec in specs if spec.name in self._allow)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Call an allowlisted tool; any other name raises ``ToolNotFoundError``."""
        if call.name not in self._allow:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)
