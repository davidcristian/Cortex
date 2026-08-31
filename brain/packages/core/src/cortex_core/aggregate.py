"""Port-preserving ``ToolRegistry`` combinators (ADR-0009 refinements addendum).

``AggregateToolRegistry`` fans one registry across several, so the filesystem and email
sidecars coexist behind the unchanged port and the same audited ``ToolDispatcher``.
``FilteredToolRegistry`` restricts one registry to an allowlist. ``SkipUnavailableToolRegistry``
marks one registry optional (ADR-0009 degraded-mode addendum). ``UngatedToolRegistry`` strips
gated tools at the subagent hand-off boundary (ADR-0013 subagent-exclusion addendum), and
``GatedToolRegistry`` stamps named remote tools ``gated`` (ADR-0022).

All are pure routing over the port, with no I/O of their own and no cached state (the one hard
rule). Aggregation and the gated-tool check resolve by a live ``describe_tools`` walk, so a tool
dropped or re-flagged server-side mid-turn fails closed instead of routing stale.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace

from cortex_core.errors import ToolError, ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec


class AggregateToolRegistry:
    """A ``ToolRegistry`` over several registries, routing each call by tool name.

    Construction order is precedence order: a name advertised by more than one registry
    belongs to the first (the ``CompositeToolRegistry`` shadowing rule). Later duplicates
    are neither advertised nor invokable. A listing failure anywhere propagates as
    ``ToolError``, so one dead server fails the call instead of shrinking the tool set.
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


class SkipUnavailableToolRegistry:
    """A ``ToolRegistry`` whose unavailable inner registry lists as empty and is reported.

    The skip-and-report degraded mode (ADR-0009 degraded-mode addendum): a listing failure
    (``ToolError``) becomes an empty advertisement plus one ``report(name, error)`` call, so an
    aggregate keeps serving its healthy sidecars and the dead one is reported on every walk.
    The reporter is a required constructor argument, so the skipping cannot be had without the
    reporting. Only discovery is softened, and ``invoke`` delegates untouched, so invoking a
    tool on an unavailable registry directly still raises; through an aggregate, an
    unadvertised tool fails closed as ``ToolNotFoundError``.
    """

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
        """Delegate untouched: only discovery is softened, never execution."""
        return await self._inner.invoke(call)


class UngatedToolRegistry:
    """A ``ToolRegistry`` with the gated tools removed, for handing to a subagent (ADR-0013).

    ``describe_tools`` drops every ``gated`` spec, and ``invoke`` raises ``ToolNotFoundError``
    for a name the inner registry currently advertises as gated (resolved by a live walk, never
    a cached view), so the exclusion is enforced rather than advisory. Prompt framing is
    unreliable on the small subagent tier, so a subagent must never hold an outbound or
    irreversible capability at all; wrapping its tool subset here makes that structural, and a
    gated tool added to the shared registry later is not visible to a subagent either.
    """

    def __init__(self, inner: ToolRegistry) -> None:
        self._inner = inner

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's ungated tools, inner order kept."""
        return tuple(spec for spec in await self._inner.describe_tools() if not spec.gated)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate an ungated call; a gated name raises ``ToolNotFoundError`` (fail closed)."""
        gated = {spec.name for spec in await self._inner.describe_tools() if spec.gated}
        if call.name in gated:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)


class GatedToolRegistry:
    """A ``ToolRegistry`` whose named tools are advertised ``gated`` (ADR-0022).

    The composition-root gating overlay for remote tools: ``McpToolRegistry`` builds specs
    generically and must never honor a sidecar's own gating claim, since a compromised server
    could then un-gate itself, so the brain declares gating here over the shared registry root.
    ``describe_tools`` stamps ``gated=True`` onto matching specs and ``invoke`` delegates
    untouched. The dispatcher enforces the gate (ADR-0013), this overlay only declares it, and
    ``UngatedToolRegistry`` downstream strips the stamped tools from subagents. A name in the
    set that no registry advertises has no effect, so a fail-closed default set costs nothing.
    """

    def __init__(self, inner: ToolRegistry, *, gated: Sequence[str]) -> None:
        if not gated:
            msg = "GatedToolRegistry needs a non-empty gated-name set"
            raise ValueError(msg)
        self._inner = inner
        self._gated = frozenset(gated)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, gated names stamped, inner order kept."""
        return tuple(
            replace(spec, gated=True) if spec.name in self._gated else spec
            for spec in await self._inner.describe_tools()
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate untouched; the dispatcher enforces the gate this overlay declares."""
        return await self._inner.invoke(call)


class FilteredToolRegistry:
    """A ``ToolRegistry`` restricted to an allowlist of tool names.

    ``describe_tools`` advertises only allowlisted names and ``invoke`` raises for anything
    else, so the filter is enforced rather than advisory. It only restricts: an allowlisted
    name the inner registry does not advertise stays unadvertised, and invoking it surfaces
    the inner registry's own not-found.

    The read-only filesystem mount stays the security boundary; keeping write tools out of
    the advertisement stops the model attempting calls the mount would answer with ``EROFS``.
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
        """Delegate an allowlisted call; any other name raises ``ToolNotFoundError``."""
        if call.name not in self._allow:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)
