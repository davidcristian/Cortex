from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from cortex_core import (
    GENERATING,
    MAX_CALLS_PER_ROUND,
    TOOL_RUNNING,
    USER_ASKED,
    CompositeToolRegistry,
    ConfirmationRequest,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    RecordingProgressSink,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    VramBudgetPlacer,
    Wait,
)
from cortex_core.delegation_wait import batch_wait

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_GATED = ToolSpec(name="send", description="Send it", parameters={}, gated=True)


class FixedClock:
    def now(self) -> datetime:
        return _AT


class WitnessingBackend:
    """Replays one step per call and records what the turn waited on while it streamed."""

    def __init__(
        self, sink: RecordingProgressSink, steps: Sequence[Sequence[InferenceEvent]]
    ) -> None:
        self._sink = sink
        self._steps = list(steps)
        self.seen: list[Wait | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(self._sink.waits.current())
        del messages
        step = self._steps[0] if len(self._steps) == 1 else self._steps.pop(0)
        for event in step:
            yield event


class WitnessingScheduler:
    """Admits every request at once, recording what the turn waited on just before."""

    def __init__(self, sink: RecordingProgressSink) -> None:
        self._sink = sink
        self.seen: list[Wait | None] = []

    @asynccontextmanager
    async def admit(self, request: PlacementRequest) -> AsyncGenerator[None, None]:
        del request
        self.seen.append(self._sink.waits.current())
        yield

    async def drain(self, *, timeout_s: float) -> bool:
        del timeout_s
        return True

    def undrain(self) -> None:
        return None


def _engine(
    sink: RecordingProgressSink, cortex: WitnessingBackend, tools: ToolDispatcher
) -> TurnEngine:
    return TurnEngine(
        InMemorySessionStore(),
        cortex,
        FixedClock(),
        capabilities=TurnCapabilities(tools=tools, progress=sink),
    )


async def test_a_spawn_inside_a_tool_call_shows_its_subtasks_not_the_call() -> None:
    sink = RecordingProgressSink()
    scheduler = WitnessingScheduler(sink)
    sub = WitnessingBackend(sink, [[TextChunk("sub done")]])
    resources = SubagentResources(
        backends={PlacementTarget.GPU: sub, PlacementTarget.CPU: sub},
        scheduler=scheduler,
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest("subagent", vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )
    roster = SubagentRoster(
        entries={"subagent": SubagentProfile(resources=resources)}, default="subagent"
    )
    store = InMemoryTaskStore()
    spawn = SpawnSubagentsTool(SubagentRunner(store, roster, FixedClock()), store, FixedClock())
    tools = ToolDispatcher(CompositeToolRegistry([spawn]), RecordingAuditSink(), FixedClock())
    call = ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["a"]})
    cortex = WitnessingBackend(sink, [[call], [TextChunk("both done")]])
    async for _ in _engine(sink, cortex, tools).handle_turn("s", "go", turn_id="t"):
        pass
    assert cortex.seen == [GENERATING, GENERATING]
    assert scheduler.seen == [batch_wait(1, 0)]
    assert sub.seen == [batch_wait(0, 1)]
    assert sink.held[:2] == (GENERATING, TOOL_RUNNING)
    assert sink.waits.current() is None


async def _send(arguments: Mapping[str, Any]) -> str:
    del arguments
    return "sent"


class WitnessingConfirmer:
    def __init__(self, sink: RecordingProgressSink) -> None:
        self._sink = sink
        self.seen: list[Wait | None] = []

    async def confirm(self, request: ConfirmationRequest) -> bool:
        del request
        self.seen.append(self._sink.waits.current())
        return True


async def test_a_confirmation_is_the_innermost_wait_of_its_tool_call() -> None:
    sink = RecordingProgressSink()
    confirmer = WitnessingConfirmer(sink)
    tools = ToolDispatcher(
        InMemoryToolRegistry({"send": (_GATED, _send)}),
        RecordingAuditSink(),
        FixedClock(),
        confirmer=confirmer,
    )
    call = ToolCall(id="c1", name="send", arguments={})
    cortex = WitnessingBackend(sink, [[call], [TextChunk("sent it")]])
    async for _ in _engine(sink, cortex, tools).handle_turn("s", "send it", turn_id="t"):
        pass
    assert confirmer.seen == [USER_ASKED]
    assert sink.held == (GENERATING, TOOL_RUNNING, USER_ASKED, GENERATING)


async def test_a_refused_call_holds_no_tool_wait() -> None:
    sink = RecordingProgressSink()
    spec = ToolSpec(name="send", description="Send it", parameters={})
    tools = ToolDispatcher(
        InMemoryToolRegistry({"send": (spec, _send)}), RecordingAuditSink(), FixedClock()
    )
    calls = [
        ToolCall(id=f"c{n}", name="send", arguments={"n": n})
        for n in range(MAX_CALLS_PER_ROUND + 1)
    ]
    cortex = WitnessingBackend(sink, [calls, [TextChunk("ok")]])
    async for _ in _engine(sink, cortex, tools).handle_turn("s", "send", turn_id="t"):
        pass
    assert sink.held.count(TOOL_RUNNING) == MAX_CALLS_PER_ROUND
