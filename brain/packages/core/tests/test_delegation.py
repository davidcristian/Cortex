"""End-to-end delegation over the fakes: a cortex turn spawns subagents (ADR-0010/0018).

Ties the increments together. The CompositeToolRegistry advertises the built-in spawn tool, the
shared tool loop dispatches it (audited), the SpawnSubagentsTool runs subagents, and their
aggregated results feed back into the cortex's next inference step. The last test proves the
whole ADR-0017 chain: untrusted read → taint ledger → dispatcher stamp → task record → the
runner's forced-robust resolution.
"""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    SUBAGENT_PROGRESS_STATE,
    CompositeToolRegistry,
    EchoInferenceBackend,
    InferenceBackend,
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
    ResourceBudgetScheduler,
    Role,
    SpawnSubagentsTool,
    StatusUpdate,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    TextChunk,
    ToolActivity,
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
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.seen.append(tuple(messages))
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


class TextBackend:
    """Yields fixed text deltas and records whether it was ever used."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas
        self.seen: list[tuple[Message, ...]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.seen.append(tuple(messages))
        for delta in self._deltas:
            yield TextChunk(delta)


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


def _counter() -> Callable[[], str]:
    ids = iter(f"st-{n}" for n in range(1, 9))
    return lambda: next(ids)


def _resources(backend: InferenceBackend, model: str) -> SubagentResources:
    return SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(8.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )


def _single_roster(backend: InferenceBackend) -> SubagentRoster:
    return SubagentRoster(
        entries={"subagent": SubagentProfile(resources=_resources(backend, "subagent"))},
        default="subagent",
    )


async def test_cortex_turn_delegates_and_consumes_the_results() -> None:
    task_store = InMemoryTaskStore()
    # A subagent tier with no tools of its own. The delegation-free subset keeps fan-out depth-1.
    runner = SubagentRunner(task_store, _single_roster(EchoInferenceBackend()), FixedClock())
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


_READ_SPEC = ToolSpec(name="read", description="", parameters={})


class OneReadThenAnswer:
    """Stateless subagent backend: read once, then answer. Whether the read already happened is
    read off the messages (a TOOL result present), so concurrent subagents share one instance
    without a counter that overlap would scramble (the test_spawn OneToolCallBackend pattern)."""

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
        yield ToolCall(id="c1", name="read", arguments={"path": "/x"})


async def test_delegation_surfaces_progress_to_the_stream_sink() -> None:
    # The whole side channel over the fakes (ADR-0010 progress addendum): the cortex spawns two
    # tool-using subagents, and the stream's ProgressSink (on TurnCapabilities) receives the
    # batch's scale plus each subagent's audited read step, while the engine's own event stream
    # carries only the cortex's own spawn_subagents chip. The engine generator is suspended inside
    # the spawn dispatch when the subagents run, so their steps reach the overlay only off the sink.
    task_store = InMemoryTaskStore()
    read_spec = ToolSpec(name="read", description="Read a file", parameters={})
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (read_spec, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    runner = SubagentRunner(
        task_store, _single_roster(OneReadThenAnswer()), FixedClock(), tools=sub_tools
    )
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    cortex_tools = ToolDispatcher(
        CompositeToolRegistry([spawn]), RecordingAuditSink(), FixedClock()
    )
    cortex_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["a", "b"]})],
            [TextChunk("both done")],
        ]
    )
    progress = RecordingProgressSink()
    engine = TurnEngine(
        InMemorySessionStore(),
        cortex_backend,
        FixedClock(),
        capabilities=TurnCapabilities(tools=cortex_tools, progress=progress),
        turn_id_factory=lambda: "t-1",
    )
    events = await _collect(engine.handle_turn("s", "do two things"))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="both done")
    # The engine's OWN stream carries the cortex's spawn_subagents chip, never the subagents':
    engine_activities = [event for event in events if isinstance(event, ToolActivity)]
    assert [activity.tool_name for activity in engine_activities] == ["spawn_subagents"]
    # The subagents' progress rode the side channel instead: scale first, then a step each.
    surfaced = progress.events
    assert surfaced[0] == StatusUpdate(
        state=SUBAGENT_PROGRESS_STATE, detail="delegating 2 subtasks"
    )
    read_steps = [event for event in surfaced if isinstance(event, ToolActivity)]
    assert [step.tool_name for step in read_steps] == ["read", "read"]
    assert all(step.summary == "Read a file" for step in read_steps)


async def test_a_subagent_reading_untrusted_content_taints_the_delegation_result() -> None:
    task_store = InMemoryTaskStore()
    # The subagent reads an (untrusted) file tool, then answers.
    sub_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="s1", name="read", arguments={"path": "/secret"})],
            [TextChunk("the file said hi")],
        ]
    )
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (_READ_SPEC, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    runner = SubagentRunner(task_store, _single_roster(sub_backend), FixedClock(), tools=sub_tools)
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


async def test_a_tainted_turns_spawn_is_forced_onto_the_robust_model_end_to_end() -> None:
    # The full ADR-0017 chain over the fakes: the cortex reads an untrusted file, THEN spawns
    # asking for the cheap model. The ledger marked the turn, the dispatcher stamped the spawn
    # call, the task carried the taint, and the runner resolved to the robust default.
    task_store = InMemoryTaskStore()
    robust, fast = TextBackend(["robust answer"]), TextBackend(["fast answer"])
    roster = SubagentRoster(
        entries={
            "subagent": SubagentProfile(resources=_resources(robust, "subagent")),
            "fast": SubagentProfile(resources=_resources(fast, "fast")),
        },
        default="subagent",
    )
    runner = SubagentRunner(task_store, roster, FixedClock())  # tool-less: only taint pins
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    cortex_tools = ToolDispatcher(
        CompositeToolRegistry(
            [spawn], remote=InMemoryToolRegistry({"read": (_READ_SPEC, _read_handler)})
        ),
        RecordingAuditSink(),
        FixedClock(),
    )
    cortex_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="c1", name="read", arguments={"path": "/mail"})],
            [
                ToolCall(
                    id="c2",
                    name="spawn_subagents",
                    arguments={"instructions": [{"instruction": "summarize", "model": "fast"}]},
                )
            ],
            [TextChunk("done")],
        ]
    )
    engine = TurnEngine(
        InMemorySessionStore(),
        cortex_backend,
        FixedClock(),
        capabilities=TurnCapabilities(tools=cortex_tools),
        turn_id_factory=lambda: "t-1",
    )
    await _collect(engine.handle_turn("s", "read then delegate"))
    task = await task_store.get_task("st-1")
    assert task is not None
    assert (task.model, task.tainted) == ("fast", True)  # the stamp rode the store
    assert robust.seen  # the robust default answered...
    assert not fast.seen  # ...and the requested cheap model never saw the hostile material
