"""Behavior tests for the ToolRegistry combinators (ADR-0009 refinements addendum)."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import pytest

from cortex_core import (
    AggregateToolRegistry,
    FilteredToolRegistry,
    GatedToolRegistry,
    InMemoryToolRegistry,
    SkipUnavailableToolRegistry,
    ToolCall,
    ToolError,
    ToolNotFoundError,
    ToolResult,
    ToolSpec,
    UngatedToolRegistry,
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
    # The dead sidecar is walked before the tool is found, so its failure propagates.
    aggregate = AggregateToolRegistry([FailingRegistry(), _registry("mail", "send")])
    with pytest.raises(ToolError, match="listing MCP tools failed"):
        await aggregate.invoke(ToolCall(id="c4", name="send", arguments={}))


async def test_skip_unavailable_lists_a_dead_inner_as_empty_and_reports() -> None:
    reports: list[tuple[str, str]] = []
    skip = SkipUnavailableToolRegistry(
        FailingRegistry(), name="mail", report=lambda n, e: reports.append((n, str(e)))
    )
    assert await skip.describe_tools() == ()
    assert reports == [("mail", "listing MCP tools failed")]


async def test_skip_unavailable_passes_a_healthy_inner_through_untouched() -> None:
    reports: list[tuple[str, str]] = []
    skip = SkipUnavailableToolRegistry(
        _registry("fs", "read"), name="fs", report=lambda n, e: reports.append((n, str(e)))
    )
    assert [spec.name for spec in await skip.describe_tools()] == ["read"]
    result = await skip.invoke(ToolCall(id="c8", name="read", arguments={}))
    assert result.content == "from fs"
    assert reports == []


async def test_skip_unavailable_softens_only_discovery_never_execution() -> None:
    # A direct invoke on the dead inner raises and is not reported: only listing is skipped.
    reports: list[tuple[str, str]] = []
    skip = SkipUnavailableToolRegistry(
        FailingRegistry(), name="mail", report=lambda n, e: reports.append((n, str(e)))
    )
    with pytest.raises(ToolError, match="never routed to"):
        await skip.invoke(ToolCall(id="c9", name="read", arguments={}))
    assert reports == []


async def test_aggregate_over_a_skipped_dead_sidecar_serves_the_healthy_ones() -> None:
    """The degraded mode end to end: healthy sidecars serve, the dead one is reported per walk."""
    reports: list[tuple[str, str]] = []
    dead = SkipUnavailableToolRegistry(
        FailingRegistry(), name="mail", report=lambda n, e: reports.append((n, str(e)))
    )
    aggregate = AggregateToolRegistry([dead, _registry("fs", "read")])
    assert [spec.name for spec in await aggregate.describe_tools()] == ["read"]
    result = await aggregate.invoke(ToolCall(id="c10", name="read", arguments={}))
    assert result.content == "from fs"
    # A tool only the dead sidecar had is unadvertised, so it is reported as not found.
    with pytest.raises(ToolNotFoundError, match="unknown tool 'search_emails'"):
        await aggregate.invoke(ToolCall(id="c11", name="search_emails", arguments={}))
    # One report per walk (describe, plus each invoke's routing walk), so a degraded aggregate
    # is never silent.
    assert [name for name, _ in reports] == ["mail", "mail", "mail"]


def _mixed_registry() -> InMemoryToolRegistry:
    """One ungated read tool next to one gated send tool (the subagent hand-off case)."""
    return InMemoryToolRegistry(
        {
            "read": (ToolSpec(name="read", description="", parameters={}), _replies("fs")),
            "send": (
                ToolSpec(name="send", description="", parameters={}, gated=True),
                _replies("mail"),
            ),
        }
    )


async def test_ungated_advertises_only_ungated_tools() -> None:
    ungated = UngatedToolRegistry(_mixed_registry())
    assert [spec.name for spec in await ungated.describe_tools()] == ["read"]


async def test_ungated_delegates_an_ungated_call() -> None:
    ungated = UngatedToolRegistry(_mixed_registry())
    result = await ungated.invoke(ToolCall(id="g1", name="read", arguments={}))
    assert result.content == "from fs"


async def test_ungated_refuses_a_gated_call_the_inner_would_run() -> None:
    # The inner registry has the gated tool, so the exclusion is enforced here and is not merely
    # advisory.
    ungated = UngatedToolRegistry(_mixed_registry())
    with pytest.raises(ToolNotFoundError, match="unknown tool 'send'"):
        await ungated.invoke(ToolCall(id="g2", name="send", arguments={}))


async def test_ungated_surfaces_the_inner_not_found_for_an_unknown_name() -> None:
    ungated = UngatedToolRegistry(_mixed_registry())
    with pytest.raises(ToolNotFoundError, match="unknown tool 'ghost'"):
        await ungated.invoke(ToolCall(id="g3", name="ghost", arguments={}))


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
    # The inner registry has the tool, so the filter is enforced here and is not merely advisory.
    filtered = FilteredToolRegistry(_registry("fs", "read", "write"), allow=["read"])
    with pytest.raises(ToolNotFoundError, match="unknown tool 'write'"):
        await filtered.invoke(ToolCall(id="c6", name="write", arguments={}))


async def test_filter_only_restricts_never_grants() -> None:
    # An allowlisted name the inner registry lacks: unadvertised, and the inner not-found surfaces.
    filtered = FilteredToolRegistry(_registry("fs", "read"), allow=["read", "ghost"])
    assert [spec.name for spec in await filtered.describe_tools()] == ["read"]
    with pytest.raises(ToolNotFoundError, match="unknown tool 'ghost'"):
        await filtered.invoke(ToolCall(id="c7", name="ghost", arguments={}))


def test_gated_overlay_requires_a_non_empty_name_set() -> None:
    with pytest.raises(ValueError, match="non-empty gated-name set"):
        GatedToolRegistry(_registry("mail", "send_email"), gated=[])


async def test_gated_overlay_stamps_named_tools_and_leaves_the_rest() -> None:
    # The composition-root declaration (ADR-0022): the remote spec arrives gated=False and
    # leaves gated=True; unnamed tools ride through untouched, inner order kept.
    inner = _registry("mail", "read_email", "send_email")
    overlay = GatedToolRegistry(inner, gated=["send_email"])
    specs = {spec.name: spec.gated for spec in await overlay.describe_tools()}
    assert specs == {"read_email": False, "send_email": True}


async def test_gated_overlay_tolerates_a_name_that_never_appears() -> None:
    # The fail-closed default set may name tools no sidecar serves, which changes nothing here.
    overlay = GatedToolRegistry(_registry("fs", "read"), gated=["send_email"])
    specs = {spec.name: spec.gated for spec in await overlay.describe_tools()}
    assert specs == {"read": False}


async def test_gated_overlay_delegates_invocation_untouched() -> None:
    # Enforcement is the dispatcher's; the overlay only declares.
    overlay = GatedToolRegistry(_registry("mail", "send_email"), gated=["send_email"])
    result = await overlay.invoke(ToolCall(id="c8", name="send_email", arguments={}))
    assert result.content == "from mail"


async def test_gated_overlay_composes_with_the_subagent_strip() -> None:
    # The end-to-end property (ADR-0022 decision 4): stamp at the shared root, and the
    # subagent-facing UngatedToolRegistry strips the stamped tool, so a subagent never sees
    # send_email at all rather than seeing it and being denied.
    root = GatedToolRegistry(_registry("mail", "read_email", "send_email"), gated=["send_email"])
    subagent_view = UngatedToolRegistry(root)
    assert [spec.name for spec in await subagent_view.describe_tools()] == ["read_email"]
    with pytest.raises(ToolNotFoundError, match="unknown tool 'send_email'"):
        await subagent_view.invoke(ToolCall(id="c9", name="send_email", arguments={}))
