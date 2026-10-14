from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import pytest

from cortex_core import (
    AggregateToolRegistry,
    ConfirmFreeToolRegistry,
    ConfirmRequiredToolRegistry,
    FilteredToolRegistry,
    InMemoryToolRegistry,
    SkipUnavailableToolRegistry,
    ToolCall,
    ToolError,
    ToolNotFoundError,
    ToolResult,
    ToolServerDownError,
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
    """A ToolRegistry whose listing always fails, as a dead sidecar's would."""

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
    assert specs[0].description == ""


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
    reports: list[tuple[str, str]] = []
    skip = SkipUnavailableToolRegistry(
        FailingRegistry(), name="mail", report=lambda n, e: reports.append((n, str(e)))
    )
    with pytest.raises(ToolError, match="never routed to"):
        await skip.invoke(ToolCall(id="c9", name="read", arguments={}))
    assert reports == []


async def test_aggregate_over_a_skipped_dead_sidecar_serves_the_healthy_ones() -> None:
    reports: list[tuple[str, str]] = []
    dead = SkipUnavailableToolRegistry(
        FailingRegistry(), name="mail", report=lambda n, e: reports.append((n, str(e)))
    )
    aggregate = AggregateToolRegistry([dead, _registry("fs", "read")])
    assert [spec.name for spec in await aggregate.describe_tools()] == ["read"]
    result = await aggregate.invoke(ToolCall(id="c10", name="read", arguments={}))
    assert result.content == "from fs"
    with pytest.raises(ToolNotFoundError, match="unknown tool 'search_emails'"):
        await aggregate.invoke(ToolCall(id="c11", name="search_emails", arguments={}))
    assert [name for name, _ in reports] == ["mail", "mail", "mail"]


class StoppingRegistry:
    """A ToolRegistry over a sidecar that lists ``names`` until ``answering`` is cleared."""

    def __init__(self, *names: str) -> None:
        self.names = names
        self.answering = True

    async def describe_tools(self) -> Sequence[ToolSpec]:
        if not self.answering:
            msg = "MCP sidecar unavailable"
            raise ToolError(msg)
        return tuple(ToolSpec(name=n, description="", parameters={}) for n in self.names)

    async def invoke(self, call: ToolCall) -> ToolResult:
        return ToolResult(call_id=call.id, content="from mail")


def _stopping_mail() -> tuple[StoppingRegistry, AggregateToolRegistry]:
    sidecar = StoppingRegistry("search_emails")
    skip = SkipUnavailableToolRegistry(sidecar, name="mail", report=lambda _n, _e: None)
    return sidecar, AggregateToolRegistry([skip, _registry("fs", "read")])


async def test_a_call_to_a_listed_tool_of_a_stopped_server_names_the_server() -> None:
    sidecar, aggregate = _stopping_mail()
    assert [spec.name for spec in await aggregate.describe_tools()] == ["search_emails", "read"]
    sidecar.answering = False
    with pytest.raises(ToolError) as raised:
        await aggregate.invoke(ToolCall(id="c12", name="search_emails", arguments={}))
    assert not isinstance(raised.value, ToolNotFoundError)
    assert (
        str(raised.value) == "the mail tool server is not answering, so 'search_emails' did not run"
    )
    with pytest.raises(ToolNotFoundError, match="unknown tool 'send_email'"):
        await aggregate.invoke(ToolCall(id="c13", name="send_email", arguments={}))


async def test_a_tool_an_answering_server_dropped_stays_unknown() -> None:
    sidecar, aggregate = _stopping_mail()
    await aggregate.describe_tools()
    sidecar.names = ()
    await aggregate.describe_tools()
    sidecar.answering = False
    with pytest.raises(ToolNotFoundError, match="unknown tool 'search_emails'"):
        await aggregate.invoke(ToolCall(id="c14", name="search_emails", arguments={}))


async def test_a_server_that_answers_again_routes_the_call() -> None:
    sidecar, aggregate = _stopping_mail()
    await aggregate.describe_tools()
    sidecar.answering = False
    with pytest.raises(ToolError, match="not answering"):
        await aggregate.invoke(ToolCall(id="c15", name="search_emails", arguments={}))
    sidecar.answering = True
    result = await aggregate.invoke(ToolCall(id="c16", name="search_emails", arguments={}))
    assert result.content == "from mail"


class CutOffRegistry:
    """A ToolRegistry whose server lists ``read`` and stops answering during each call."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (ToolSpec(name="read", description="", parameters={}),)

    async def invoke(self, call: ToolCall) -> ToolResult:
        del call
        msg = "MCP sidecar unavailable"
        raise ToolServerDownError(msg)


async def test_a_call_cut_off_by_a_stopped_server_names_the_server() -> None:
    skip = SkipUnavailableToolRegistry(
        CutOffRegistry(), name="filesystem", report=lambda _n, _e: None
    )
    with pytest.raises(ToolError) as raised:
        await skip.invoke(ToolCall(id="c17", name="read", arguments={}))
    assert not isinstance(raised.value, ToolServerDownError)
    assert str(raised.value) == (
        "the filesystem tool server stopped answering during this call, so the call did not "
        "finish; this says nothing about the file or item the call named"
    )
    assert isinstance(raised.value.__cause__, ToolServerDownError)


def _mixed_registry() -> InMemoryToolRegistry:
    """One open read tool next to one send tool that needs approval."""
    return InMemoryToolRegistry(
        {
            "read": (ToolSpec(name="read", description="", parameters={}), _replies("fs")),
            "send": (
                ToolSpec(name="send", description="", parameters={}, confirm_required=True),
                _replies("mail"),
            ),
        }
    )


async def test_confirm_free_advertises_only_confirm_free_tools() -> None:
    confirm_free = ConfirmFreeToolRegistry(_mixed_registry())
    assert [spec.name for spec in await confirm_free.describe_tools()] == ["read"]


async def test_confirm_free_delegates_an_confirm_free_call() -> None:
    confirm_free = ConfirmFreeToolRegistry(_mixed_registry())
    result = await confirm_free.invoke(ToolCall(id="g1", name="read", arguments={}))
    assert result.content == "from fs"


async def test_confirm_free_refuses_a_confirm_required_call_the_inner_would_run() -> None:
    confirm_free = ConfirmFreeToolRegistry(_mixed_registry())
    with pytest.raises(ToolNotFoundError, match="unknown tool 'send'"):
        await confirm_free.invoke(ToolCall(id="g2", name="send", arguments={}))


async def test_confirm_free_surfaces_the_inner_not_found_for_an_unknown_name() -> None:
    confirm_free = ConfirmFreeToolRegistry(_mixed_registry())
    with pytest.raises(ToolNotFoundError, match="unknown tool 'ghost'"):
        await confirm_free.invoke(ToolCall(id="g3", name="ghost", arguments={}))


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
    filtered = FilteredToolRegistry(_registry("fs", "read", "write"), allow=["read"])
    with pytest.raises(ToolNotFoundError, match="unknown tool 'write'"):
        await filtered.invoke(ToolCall(id="c6", name="write", arguments={}))


async def test_filter_only_restricts_never_grants() -> None:
    filtered = FilteredToolRegistry(_registry("fs", "read"), allow=["read", "ghost"])
    assert [spec.name for spec in await filtered.describe_tools()] == ["read"]
    with pytest.raises(ToolNotFoundError, match="unknown tool 'ghost'"):
        await filtered.invoke(ToolCall(id="c7", name="ghost", arguments={}))


def test_confirm_required_overlay_requires_a_non_empty_name_set() -> None:
    with pytest.raises(
        ValueError, match="ConfirmRequiredToolRegistry needs at least one tool name to confirm"
    ):
        ConfirmRequiredToolRegistry(_registry("mail", "send_email"), names=[])


async def test_confirm_required_overlay_stamps_named_tools_and_leaves_the_rest() -> None:
    inner = _registry("mail", "read_email", "send_email")
    overlay = ConfirmRequiredToolRegistry(inner, names=["send_email"])
    specs = {spec.name: spec.confirm_required for spec in await overlay.describe_tools()}
    assert specs == {"read_email": False, "send_email": True}


async def test_confirm_required_overlay_tolerates_a_name_that_never_appears() -> None:
    overlay = ConfirmRequiredToolRegistry(_registry("fs", "read"), names=["send_email"])
    specs = {spec.name: spec.confirm_required for spec in await overlay.describe_tools()}
    assert specs == {"read": False}


async def test_confirm_required_overlay_delegates_invocation_untouched() -> None:
    overlay = ConfirmRequiredToolRegistry(_registry("mail", "send_email"), names=["send_email"])
    result = await overlay.invoke(ToolCall(id="c8", name="send_email", arguments={}))
    assert result.content == "from mail"


async def test_confirm_required_overlay_composes_with_the_subagent_strip() -> None:
    root = ConfirmRequiredToolRegistry(
        _registry("mail", "read_email", "send_email"), names=["send_email"]
    )
    subagent_view = ConfirmFreeToolRegistry(root)
    assert [spec.name for spec in await subagent_view.describe_tools()] == ["read_email"]
    with pytest.raises(ToolNotFoundError, match="unknown tool 'send_email'"):
        await subagent_view.invoke(ToolCall(id="c9", name="send_email", arguments={}))
