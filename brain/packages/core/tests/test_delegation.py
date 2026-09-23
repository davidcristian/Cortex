from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    CALLING,
    QUEUED,
    SUBAGENT_PROGRESS_STATE,
    CompositeToolRegistry,
    EchoInferenceBackend,
    GenerationBounds,
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
    TurnStamp,
    VramBudgetPlacer,
)

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _AT


class ScriptedCortexBackend:
    """Cortex backend that replays per-step events and records the messages it was shown."""

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
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(tuple(messages))
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


class TextBackend:
    """Yields fixed text deltas and records whether it was used."""

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
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
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
    runner = SubagentRunner(task_store, _single_roster(EchoInferenceBackend()), FixedClock())
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
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
    )
    events = await _collect(engine.handle_turn("s", "do two things", turn_id="t-1"))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="delegating... both done")
    (audit,) = sink.records
    assert (audit.name, audit.ok) == ("spawn_subagents", True)
    _, second_step = backend.seen
    tool_msg = second_step[-1]
    assert tool_msg.role is Role.TOOL
    assert tool_msg.tool_call_id == "c1"
    assert tool_msg.text == "[subagent 1] reply 1: task A\n\n[subagent 2] reply 1: task B"


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"contents of {arguments['path']}"


_READ_SPEC = ToolSpec(name="read", description="", parameters={})


class OneReadThenAnswer:
    """Stateless subagent backend: read once, then answer."""

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
        if any(message.role is Role.TOOL for message in messages):
            yield TextChunk("done")
            return
        yield ToolCall(id="c1", name="read", arguments={"path": "/x"})


async def test_delegation_surfaces_progress_to_the_stream_sink() -> None:
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
    )
    events = await _collect(engine.handle_turn("s", "do two things", turn_id="t-1"))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="both done")
    engine_activities = [event for event in events if isinstance(event, ToolActivity)]
    assert [activity.tool_name for activity in engine_activities] == ["spawn_subagents"]
    surfaced = progress.events
    assert surfaced[:2] == (
        StatusUpdate(state=CALLING, detail="waiting for a tool to finish"),
        StatusUpdate(state=QUEUED, detail="2 subtasks waiting for room to run"),
    )
    assert StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail="1 subtask running") in surfaced
    read_steps = [event for event in surfaced if isinstance(event, ToolActivity)]
    assert [step.tool_name for step in read_steps] == ["read", "read"]
    assert all(step.summary == "Read a file" for step in read_steps)


async def test_a_subagent_reading_untrusted_content_taints_the_delegation_result() -> None:
    task_store = InMemoryTaskStore()
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
    )
    await _collect(engine.handle_turn("s", "delegate", turn_id="t-1"))
    _, second_step = cortex_backend.seen
    spawn_msg = second_step[-1]
    assert spawn_msg.role is Role.TOOL
    assert spawn_msg.text.startswith("<untrusted-tool-output id=")
    assert "the file said hi" in spawn_msg.text


async def test_a_tainted_turns_spawn_is_forced_onto_the_default_model_end_to_end() -> None:
    task_store = InMemoryTaskStore()
    default_backend, fast = TextBackend(["default answer"]), TextBackend(["fast answer"])
    roster = SubagentRoster(
        entries={
            "subagent": SubagentProfile(resources=_resources(default_backend, "subagent")),
            "fast": SubagentProfile(resources=_resources(fast, "fast")),
        },
        default="subagent",
    )
    runner = SubagentRunner(task_store, roster, FixedClock())
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
    )
    await _collect(engine.handle_turn("s", "read then delegate", turn_id="t-1"))
    task = await task_store.get_task("st-1")
    assert task is not None
    assert (task.model, task.tainted) == ("fast", True)
    assert default_backend.seen
    assert not fast.seen


async def test_a_delegated_call_is_audited_under_the_turn_that_spawned_it() -> None:
    task_store = InMemoryTaskStore()
    sub_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="s1", name="read", arguments={"path": "/notes"})],
            [TextChunk("summarized")],
        ]
    )
    sub_sink = RecordingAuditSink()
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (_READ_SPEC, _read_handler)}), sub_sink, FixedClock()
    )
    runner = SubagentRunner(task_store, _single_roster(sub_backend), FixedClock(), tools=sub_tools)
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    cortex_sink = RecordingAuditSink()
    cortex_tools = ToolDispatcher(CompositeToolRegistry([spawn]), cortex_sink, FixedClock())
    cortex_backend = ScriptedCortexBackend(
        [
            [ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["summarize"]})],
            [TextChunk("relayed")],
        ]
    )
    engine = TurnEngine(
        InMemorySessionStore(),
        cortex_backend,
        FixedClock(),
        capabilities=TurnCapabilities(tools=cortex_tools),
    )
    await _collect(engine.handle_turn("s-9", "delegate", turn_id="t-9"))
    (spawn_line,) = cortex_sink.records
    assert (spawn_line.name, spawn_line.session_id, spawn_line.turn_id, spawn_line.task_id) == (
        "spawn_subagents",
        "s-9",
        "t-9",
        "",
    )
    task = await task_store.get_task("st-1")
    assert task is not None
    assert (task.session_id, task.turn_id) == ("s-9", "t-9")
    (read_line,) = sub_sink.records
    assert (read_line.name, read_line.session_id, read_line.turn_id, read_line.task_id) == (
        "read",
        "s-9",
        "t-9",
        "st-1",
    )
    assert (task.item_id, read_line.item_id) == ("", "")
    _, second_step = sub_backend.seen
    assert second_step[-1].turn_id == "st-1"


async def test_a_ticker_rooted_subagent_names_its_chat_and_no_turn() -> None:
    task_store = InMemoryTaskStore()
    sub_backend = ScriptedCortexBackend(
        [[ToolCall(id="s1", name="read", arguments={"path": "/notes"})], [TextChunk("done")]]
    )
    sub_sink = RecordingAuditSink()
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (_READ_SPEC, _read_handler)}), sub_sink, FixedClock()
    )
    runner = SubagentRunner(task_store, _single_roster(sub_backend), FixedClock(), tools=sub_tools)
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    dispatcher = ToolDispatcher(CompositeToolRegistry([spawn]), RecordingAuditSink(), FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="schedule-r1", name="spawn_subagents", arguments={"instructions": ["do it"]}),
        stamp=TurnStamp(session_id="chat-1"),
    )
    (read_line,) = sub_sink.records
    assert (read_line.session_id, read_line.turn_id, read_line.task_id) == ("chat-1", "", "st-1")


async def test_a_fires_delegate_names_the_item_that_fired_it() -> None:
    task_store = InMemoryTaskStore()
    sub_backend = ScriptedCortexBackend(
        [[ToolCall(id="s1", name="read", arguments={"path": "/notes"})], [TextChunk("done")]]
    )
    sub_sink = RecordingAuditSink()
    sub_tools = ToolDispatcher(
        InMemoryToolRegistry({"read": (_READ_SPEC, _read_handler)}), sub_sink, FixedClock()
    )
    runner = SubagentRunner(task_store, _single_roster(sub_backend), FixedClock(), tools=sub_tools)
    spawn = SpawnSubagentsTool(runner, task_store, FixedClock(), task_id_factory=_counter())
    fire_sink = RecordingAuditSink()
    dispatcher = ToolDispatcher(CompositeToolRegistry([spawn]), fire_sink, FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="schedule-r1", name="spawn_subagents", arguments={"instructions": ["do it"]}),
        stamp=TurnStamp(session_id="chat-1", item_id="r-1"),
    )
    task = await task_store.get_task("st-1")
    assert task is not None
    assert task.item_id == "r-1"
    (fire_line,) = fire_sink.records
    (read_line,) = sub_sink.records
    assert (fire_line.name, fire_line.item_id, fire_line.turn_id) == (
        "spawn_subagents",
        "r-1",
        "",
    )
    assert (read_line.name, read_line.item_id, read_line.task_id, read_line.turn_id) == (
        "read",
        "r-1",
        "st-1",
        "",
    )
