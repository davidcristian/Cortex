"""Port-preserving ToolRegistry combinators (ADR-0009 refinements addendum).

``AggregateToolRegistry`` fans one ``ToolRegistry`` across several. It is the multi-server
refinement that lets the filesystem and email sidecars coexist behind the unchanged port and
the same audited ``ToolDispatcher``. ``FilteredToolRegistry`` restricts one registry to an
allowlist. This is the advertised-tool refinement that stops the model seeing write tools the
read-only mount would only ``EROFS`` (the mount stays the security boundary; this is UX plus
defense in depth). Both are pure routing over the port: no I/O of their own, no cached state
(the one hard rule). Aggregation resolves ownership by a live ``describe_tools`` walk, so a
tool dropped server-side mid-turn fails closed instead of routing stale.
"""

from collections.abc import Sequence

from cortex_core.errors import ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec


class AggregateToolRegistry:
    """A ``ToolRegistry`` over several registries, routing each call by tool name.

    Construction order is precedence order: a name advertised by more than one registry
    belongs to the first (the ``CompositeToolRegistry`` shadowing rule). Later duplicates
    are neither advertised nor invokable. A listing failure anywhere propagates as
    ``ToolError``: one dead server is a loud failure, never a silently smaller tool set.
    """

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
        """Route to the first registry currently advertising ``call.name``.

        Ownership is resolved live (no cached routing table): the walk re-lists each
        registry until one advertises the name; none advertising it raises
        ``ToolNotFoundError``.
        """
        for registry in self._registries:
            names = {spec.name for spec in await registry.describe_tools()}
            if call.name in names:
                return await registry.invoke(call)
        msg = f"unknown tool {call.name!r}"
        raise ToolNotFoundError(msg)


class FilteredToolRegistry:
    """A ``ToolRegistry`` restricted to an allowlist of tool names.

    ``describe_tools`` advertises only allowlisted names; ``invoke`` refuses anything else,
    so the filter is a real layer, not advisory. It only *restricts*. An allowlisted name
    the inner registry does not advertise stays unadvertised, and invoking it surfaces the
    inner registry's own not-found.
    """

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
        """Delegate an allowlisted call; refuse any other name as not found."""
        if call.name not in self._allow:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)
