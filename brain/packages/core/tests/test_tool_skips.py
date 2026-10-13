from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from cortex_core import (
    FORGOING_STATE,
    AggregateToolRegistry,
    ConfirmFreeToolRegistry,
    ConfirmRequiredToolRegistry,
    DispatchPolicy,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    RecordingProgressSink,
    SkipUnavailableToolRegistry,
    StatusUpdate,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
    list_tools,
    skipped_detail,
)
from cortex_core.tool_skips import note_skipped


class DownRegistry:
    """A ToolRegistry whose listing fails, as a stopped sidecar's does."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        msg = "MCP sidecar unavailable"
        raise ToolError(msg)

    async def invoke(self, call: ToolCall) -> ToolResult:
        del call
        msg = "MCP sidecar unavailable"
        raise ToolError(msg)


class ToolsSeenBackend:
    """Answers ``ok`` and records the tool names each completion was offered."""

    def __init__(self) -> None:
        self.offered: list[list[str]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, schema, bounds
        self.offered.append([spec.name for spec in tools])
        yield TextChunk("ok")


async def _replies(arguments: Mapping[str, Any]) -> str:
    del arguments
    return "done"


def _healthy(*names: str) -> InMemoryToolRegistry:
    return InMemoryToolRegistry(
        {n: (ToolSpec(name=n, description="", parameters={}), _replies) for n in names}
    )


def _ignore(name: str, error: ToolError) -> None:
    del name, error


def _skip(inner: ToolRegistry, name: str) -> SkipUnavailableToolRegistry:
    return SkipUnavailableToolRegistry(inner, name=name, report=_ignore)


async def _turn(
    registry: ToolRegistry, progress: RecordingProgressSink | None
) -> tuple[list[TurnEvent], ToolsSeenBackend]:
    backend = ToolsSeenBackend()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), SystemClock())
    caps = TurnCapabilities(tools=dispatcher, progress=progress)
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", "hi", turn_id="t-1")]
    return events, backend


async def test_a_down_tool_server_costs_the_turn_its_tools_and_says_which() -> None:
    progress = RecordingProgressSink()
    registry = AggregateToolRegistry(
        [_skip(_healthy("search_emails"), "email"), _skip(DownRegistry(), "filesystem")]
    )

    events, backend = await _turn(registry, progress)

    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="ok")
    assert backend.offered == [["search_emails"]]
    assert progress.events == (
        StatusUpdate(
            state=FORGOING_STATE,
            detail=(
                "the filesystem tool server is not answering, "
                "so this turn is answered without its tools"
            ),
        ),
    )


async def test_every_down_tool_server_is_named_once_in_one_status() -> None:
    progress = RecordingProgressSink()
    registry = AggregateToolRegistry(
        [
            _skip(DownRegistry(), "email"),
            _skip(DownRegistry(), "files"),
            _skip(DownRegistry(), "web"),
        ]
    )

    events, backend = await _turn(registry, progress)

    assert isinstance(events[-1], TurnCompleted)
    assert backend.offered == [[]]
    assert progress.events == (
        StatusUpdate(
            state=FORGOING_STATE,
            detail=(
                "the email, files and web tool servers are not answering, "
                "so this turn is answered without their tools"
            ),
        ),
    )


async def test_healthy_tool_servers_send_no_status() -> None:
    progress = RecordingProgressSink()

    await _turn(_skip(_healthy("read_text_file"), "filesystem"), progress)

    assert progress.events == ()


async def test_a_turn_with_no_progress_sink_still_answers_without_the_down_server() -> None:
    events, backend = await _turn(_skip(DownRegistry(), "filesystem"), None)

    assert isinstance(events[-1], TurnCompleted)
    assert backend.offered == [[]]


class TwiceNoting:
    """A lister whose one walk reports the same server twice."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        note_skipped("filesystem")
        note_skipped("filesystem")
        return ()


async def test_a_server_reported_twice_in_one_listing_is_named_once() -> None:
    progress = RecordingProgressSink()

    await list_tools(TwiceNoting(), progress)

    assert progress.events == (
        StatusUpdate(state=FORGOING_STATE, detail=skipped_detail(["filesystem"])),
    )


async def test_a_skip_outside_a_listing_reaches_no_turn() -> None:
    note_skipped("filesystem")
    progress = RecordingProgressSink()

    await list_tools(_healthy("read_text_file"), progress)

    assert progress.events == ()


async def test_a_routing_walk_after_the_listing_adds_no_status() -> None:
    progress = RecordingProgressSink()
    registry = AggregateToolRegistry([_skip(DownRegistry(), "email"), _healthy("read")])
    await list_tools(registry, progress)

    result = await registry.invoke(ToolCall(id="c1", name="read", arguments={}))

    assert result.content == "done"
    assert len(progress.events) == 1


class FlappingRegistry:
    """A sidecar whose first listing fails and whose later ones answer, as a restarting one does."""

    def __init__(self) -> None:
        self.listings = 0
        self.sent: list[ToolCall] = []

    async def describe_tools(self) -> Sequence[ToolSpec]:
        self.listings += 1
        if self.listings == 1:
            msg = "MCP sidecar unavailable"
            raise ToolError(msg)
        return (ToolSpec(name="send_email", description="", parameters={}),)

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.sent.append(call)
        return ToolResult(call_id=call.id, content="sent")


async def test_a_subagent_cannot_send_through_a_sidecar_its_strip_found_down() -> None:
    sidecar = FlappingRegistry()
    root = ConfirmRequiredToolRegistry(
        AggregateToolRegistry([_skip(sidecar, "email"), _healthy("read")]), names=("send_email",)
    )
    dispatcher = ToolDispatcher(
        ConfirmFreeToolRegistry(root),
        RecordingAuditSink(),
        SystemClock(),
        policy=DispatchPolicy(confirm_names=("send_email",)),
    )

    result = await dispatcher.dispatch(ToolCall(id="c1", name="send_email", arguments={}))

    assert result.is_error
    assert sidecar.sent == []
