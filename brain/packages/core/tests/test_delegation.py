"""End-to-end delegation over the fakes: a cortex turn spawns subagents (ADR-0010).

Ties increment 2 together. The CompositeToolRegistry advertises the built-in spawn tool, the
shared tool loop dispatches it (audited), the SpawnSubagentsTool runs subagents, and their
aggregated results feed back into the cortex's next inference step.
"""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    CompositeToolRegistry,
    EchoInferenceBackend,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    Role,
    SpawnSubagentsTool,
    SubagentResources,
    SubagentRunner,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
    VramBudgetPlacer,
)

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _AT


class ScriptedCortexBackend:
    """Cortex backend: replays per-step events and records the messages it was shown."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0
        self.seen: list[tuple[Message, ...]] = []

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools
        self.seen.append(tuple(messages))
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


def _counter() -> Callable[[], str]:
    ids = iter(f"st-{n}" for n in range(1, 9))
    return lambda: next(ids)


async def test_cortex_turn_delegates_and_consumes_the_results() -> None:
    task_store = InMemoryTaskStore()
    # A subagent tier with no tools of its own. The delegation-free subset keeps fan-out depth-1.
    echo = EchoInferenceBackend()
    resources = SubagentResources(
        backends={PlacementTarget.GPU: echo, PlacementTarget.CPU: echo},
        scheduler=ResourceBudgetScheduler(8.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest("subagent", vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )
    runner = SubagentRunner(task_store, resources, FixedClock())
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    # The cortex's tools: the built-in spawn tool only (no remote MCP registry in this test).
    sink = RecordingAuditSink()
    cortex_tools = ToolDispatcher(CompositeToolRegistry([spawn]), sink, FixedClock())
    backend = ScriptedCortexBackend(
        [
            [
                TextChunk("delegating... "),
                ToolCall(
                    id="c1",
                    name="spawn_subagents",
                    arguments={"instructions": ["task A", "task B"]},
                ),
            ],
            [TextChunk("both done")],
        ]
    )
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        FixedClock(),
        capabilities=TurnCapabilities(tools=cortex_tools),
        turn_id_factory=lambda: "t-1",
    )
    events = await _collect(engine.handle_turn("s", "do two things"))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="delegating... both done")
    # The spawn tool ran once and was audited as a success.
    (audit,) = sink.records
    assert (audit.name, audit.ok) == ("spawn_subagents", True)
    # Step 2 saw the aggregated subagent results fed back as a TOOL message keyed to the call.
    _, second_step = backend.seen
    tool_msg = second_step[-1]
    assert tool_msg.role is Role.TOOL
    assert tool_msg.tool_call_id == "c1"
    # Clean subagents (no untrusted reads) -> the aggregate is trusted, so it is not fenced.
    assert tool_msg.text == "[subagent 1] reply 1: task A\n\n[subagent 2] reply 1: task B"


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"contents of {arguments['path']}"


async def test_a_subagent_reading_untrusted_content_taints_the_delegation_result() -> None:
    task_store = InMemoryTaskStore()
    # The subagent reads an (untrusted) file tool, then answers.
    sub_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="s1", name="read", arguments={"path": "/secret"})],
            [TextChunk("the file said hi")],
        ]
    )
    resources = SubagentResources(
        backends={PlacementTarget.GPU: sub_backend, PlacementTarget.CPU: sub_backend},
        scheduler=ResourceBudgetScheduler(8.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest("subagent", vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )
    read_spec = ToolSpec(name="read", description="", parameters={})
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (read_spec, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    runner = SubagentRunner(task_store, resources, FixedClock(), tools=sub_tools)
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    cortex_tools = ToolDispatcher(
        CompositeToolRegistry([spawn]), RecordingAuditSink(), FixedClock()
    )
    cortex_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["read it"]})],
            [TextChunk("relayed")],
        ]
    )
    engine = TurnEngine(
        InMemorySessionStore(),
        cortex_backend,
        FixedClock(),
        capabilities=TurnCapabilities(tools=cortex_tools),
        turn_id_factory=lambda: "t-1",
    )
    await _collect(engine.handle_turn("s", "delegate"))
    # The subagent read untrusted content, so the aggregated spawn result feeds back to the
    # cortex fenced as untrusted data. The taint propagated up (ADR-0013).
    _, second_step = cortex_backend.seen
    spawn_msg = second_step[-1]
    assert spawn_msg.role is Role.TOOL
    assert spawn_msg.text.startswith("<untrusted-tool-output id=")
    assert "the file said hi" in spawn_msg.text
