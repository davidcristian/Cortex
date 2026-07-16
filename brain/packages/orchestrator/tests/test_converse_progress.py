"""Subagent progress reaches the overlay over the real converse() stream (ADR-0010 progress).

A delegating cortex turn suspends its own generator inside the spawn dispatch, so a subagent's
steps can only reach the wire through this stream's SeamProgressSink. This wires a real
SpawnSubagentsTool into the cortex, spawns a tool-using subagent, and asserts the batch's scale
(a StatusUpdate) and the subagent's audited step (a ToolActivity) both arrive as ServerEvents,
alongside the cortex's own spawn_subagents chip.
"""

from collections.abc import AsyncIterator, Mapping, Sequence

from cortex_core import (
    CompositeToolRegistry,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    ProgressSink,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    Role,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SystemClock,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    VramBudgetPlacer,
)
from cortex_core import Confirmer as ConfirmerPort
from cortex_orchestrator import EngineFactory, converse
from cortex_seam import ClientEvent, ServerEvent, UserTurn


async def _read(arguments: Mapping[str, object]) -> str:
    return f"contents of {arguments['path']}"


_READ_SPEC = ToolSpec(name="read", description="Read a file", parameters={})


class _OneReadThenAnswer:
    """Stateless subagent backend: read once, then answer (read off the messages, so a batch's
    concurrent subagents share one instance without a counter overlap would scramble)."""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        if any(message.role is Role.TOOL for message in messages):
            yield TextChunk("done")
            return
        yield ToolCall(id="s1", name="read", arguments={"path": "/x"})


class _SpawnThenReply:
    """Cortex backend: spawn one subagent, then reply once its result feeds back."""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        if any(message.role is Role.TOOL for message in messages):
            yield TextChunk("all done")
            return
        yield ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["look it up"]})


def _delegating_factory() -> EngineFactory:
    """An engine whose cortex delegates to a tool-using subagent, per stream (ADR-0010)."""

    def make(_confirmer: ConfirmerPort, progress: ProgressSink) -> TurnEngine:
        task_store = InMemoryTaskStore()
        roster = SubagentRoster(
            entries={
                "subagent": SubagentProfile(
                    resources=SubagentResources(
                        backends={
                            PlacementTarget.GPU: _OneReadThenAnswer(),
                            PlacementTarget.CPU: _OneReadThenAnswer(),
                        },
                        scheduler=ResourceBudgetScheduler(8.0, 8.0),
                        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
                        request=PlacementRequest("subagent", vram_gb=2.0, cpus=2.0, memory_gb=2.0),
                    )
                )
            },
            default="subagent",
        )
        sub_tools = ToolDispatcher(
            InMemoryToolRegistry({"read": (_READ_SPEC, _read)}), RecordingAuditSink(), SystemClock()
        )
        runner = SubagentRunner(task_store, roster, SystemClock(), tools=sub_tools)
        spawn = SpawnSubagentsTool(runner, task_store, SystemClock())
        cortex_tools = ToolDispatcher(
            CompositeToolRegistry([spawn]), RecordingAuditSink(), SystemClock()
        )
        return TurnEngine(
            InMemorySessionStore(),
            _SpawnThenReply(),
            SystemClock(),
            capabilities=TurnCapabilities(tools=cortex_tools, progress=progress),
        )

    return make


async def _events_from(*events: ClientEvent) -> AsyncIterator[ClientEvent]:
    for event in events:
        yield event


async def _collect(stream: AsyncIterator[ServerEvent]) -> list[ServerEvent]:
    return [event async for event in stream]


def _user_turn(text: str) -> ClientEvent:
    return ClientEvent(session_id="s", user_turn=UserTurn(text=text))


async def test_a_delegating_turn_surfaces_subagent_progress_on_the_wire() -> None:
    events = await _collect(converse(_delegating_factory(), _events_from(_user_turn("delegate"))))
    statuses = [e.status for e in events if e.WhichOneof("event") == "status"]
    activities = [e.tool_activity for e in events if e.WhichOneof("event") == "tool_activity"]
    names = [a.tool_name for a in activities]
    # The batch's scale, brain-authored, reached the overlay:
    assert any(s.state == "delegating" and s.detail == "delegating 1 subtask" for s in statuses)
    # Both the cortex's own spawn chip and the subagent's audited read step reached it, the read
    # only reachable through the side channel (the turn was suspended inside the spawn dispatch):
    assert "spawn_subagents" in names
    assert ("read", "Read a file") in [(a.tool_name, a.summary) for a in activities]
    # The reply still completed after the delegated work fed back.
    assert any(e.WhichOneof("event") == "turn_complete" for e in events)
