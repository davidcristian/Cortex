"""Port-preserving ToolRegistry combinators (ADR-0009 refinements addendum).

``AggregateToolRegistry`` fans one ``ToolRegistry`` across several. It is the multi-server
refinement that lets the filesystem and email sidecars coexist behind the unchanged port and
the same audited ``ToolDispatcher``. ``FilteredToolRegistry`` restricts one registry to an
allowlist. This is the advertised-tool refinement that stops the model seeing write tools the
read-only mount would only ``EROFS`` (the mount stays the security boundary; this is UX plus
defense in depth). ``SkipUnavailableToolRegistry`` marks one registry optional, giving the
skip-and-report degraded mode (ADR-0009 degraded-mode addendum) that keeps an aggregate
serving its healthy sidecars while a dead one is reported, never silently dropped.
``UngatedToolRegistry`` strips gated tools at the subagent hand-off boundary (ADR-0013
subagent-exclusion addendum): a jailbroken subagent must have nothing dangerous to call, not
merely be denied at the gate. ``GatedToolRegistry`` stamps named remote tools ``gated``, forming
the composition-root gating overlay (ADR-0022): gating is declared in code under review on
the brain side, never by a sidecar's own metadata. All are pure routing over the port: no
I/O of their own, no cached state (the one hard rule). Aggregation and the gated-tool
check resolve by a live ``describe_tools`` walk, so a tool dropped or re-flagged
server-side mid-turn fails closed instead of routing stale.
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


class SkipUnavailableToolRegistry:
    """A ``ToolRegistry`` whose unavailable inner registry lists as empty and is reported.

    The skip-and-report degraded mode (ADR-0009 degraded-mode addendum): a listing failure
    (``ToolError``) becomes an empty advertisement plus one ``report(name, error)`` call, so
    an aggregate keeps serving its healthy sidecars while the operator hears about the dead
    one on every walk, degraded but never silent. The reporter is mandatory: there is no way
    to construct the skipping behavior without the reporting. Only discovery is softened, and
    ``invoke`` delegates untouched, so directly invoking a tool on an unavailable registry
    still fails loudly; through an aggregate, an unadvertised tool fails closed as
    ``ToolNotFoundError``.
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
        """Delegate untouched. Execution failures are never skipped, only discovery is."""
        return await self._inner.invoke(call)


class UngatedToolRegistry:
    """A ``ToolRegistry`` stripped of gated tools is what a subagent may be handed (ADR-0013).

    ``describe_tools`` drops every ``gated`` spec; ``invoke`` refuses a name the inner
    registry currently advertises as gated (resolved by a live walk, never a cached view), so
    the exclusion is a real layer, not advisory. Framing is unreliable on the small subagent
    tier, so a subagent must never *hold* an outbound/irreversible capability. Wrapping its
    tool subset here makes that structural: a gated tool added to the shared registry later
    simply does not exist from a subagent's point of view.
    """

    def __init__(self, inner: ToolRegistry) -> None:
        self._inner = inner

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's ungated tools, inner order kept."""
        return tuple(spec for spec in await self._inner.describe_tools() if not spec.gated)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate an ungated call; refuse a gated name as not found (fail closed)."""
        gated = {spec.name for spec in await self._inner.describe_tools() if spec.gated}
        if call.name in gated:
            msg = f"unknown tool {call.name!r}"
            raise ToolNotFoundError(msg)
        return await self._inner.invoke(call)


class GatedToolRegistry:
    """A ``ToolRegistry`` whose named tools are advertised ``gated`` (ADR-0022).

    The composition-root gating overlay for *remote* tools: ``McpToolRegistry`` builds specs
    generically and must never honor a sidecar's own gating claim (a compromised server
    could un-gate itself), so the brain declares gating here, over the shared registry root.
    ``describe_tools`` stamps ``gated=True`` onto matching specs; ``invoke`` delegates
    untouched. The *dispatcher* enforces the gate (ADR-0013), this overlay only declares
    it, and ``UngatedToolRegistry`` downstream strips the stamped tools from subagents. A
    name that never appears is harmless, so a fail-closed default set costs nothing.
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
        """Delegate untouched. Enforcement is the dispatcher's, declaration is ours."""
        return await self._inner.invoke(call)


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
