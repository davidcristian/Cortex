import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from cortex_core import (
    ATTEMPTS_PER_ADMISSION,
    BUDGET_EXHAUSTED_MSG,
    DispatchBudget,
    GenerationBounds,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    PlainFormatter,
    ReasoningChunk,
    RecordingAuditSink,
    RecordingProgressSink,
    ResourceBudgetScheduler,
    Role,
    SubagentPlacer,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SubagentTask,
    TextChunk,
    ToolActivity,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    VramBudgetPlacer,
)
from cortex_core.subagent_reply import REPLY_INSTRUCTION

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_RUNNER_LOGGER = "cortex_core.runner"


class FixedClock:
    """A clock fixed at one instant."""

    def now(self) -> datetime:
        return _AT


class TextBackend:
    """Yields fixed text deltas and keeps the messages it was handed."""

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


class ScriptedBackend:
    """Replays a per-step list of events: text deltas, tool calls, or both."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        step = self._steps[self._call]
        self._call += 1
        for event in step:
            yield event


class FailingBackend:
    """Yields one delta, then fails with the typed inference error."""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        yield TextChunk("partial ")
        msg = "backend exploded"
        raise InferenceError(msg)


class SchemaRecordingBackend:
    """Records the schema and the messages it was handed, and yields fixed text."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas
        self.schemas: list[JsonSchema | None] = []
        self.asked: list[tuple[Message, ...]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, bounds
        self.schemas.append(schema)
        self.asked.append(tuple(messages))
        for delta in self._deltas:
            yield TextChunk(delta)


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"read {arguments['path']}"


_REQUEST = PlacementRequest("subagent", vram_gb=2.0, cpus=2.0, memory_gb=2.0)


def _resources(
    gpu: InferenceBackend, cpu: InferenceBackend, placer: SubagentPlacer
) -> SubagentResources:
    return SubagentResources(
        backends={PlacementTarget.GPU: gpu, PlacementTarget.CPU: cpu},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=placer,
        request=_REQUEST,
    )


def _roster(resources: SubagentResources, **extra: SubagentResources) -> SubagentRoster:
    entries = {"subagent": SubagentProfile(resources=resources)} | {
        name: SubagentProfile(resources=res) for name, res in extra.items()
    }
    return SubagentRoster(entries=entries, default="subagent")


def _runner(
    store: InMemoryTaskStore,
    backend: InferenceBackend,
    *,
    tools: ToolDispatcher | None = None,
    constrain_output: bool = False,
) -> SubagentRunner:
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    roster = _roster(_resources(backend, backend, placer))
    return SubagentRunner(
        store, roster, FixedClock(), tools=tools, constrain_output=constrain_output
    )


async def test_runs_a_plain_task_and_persists_the_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="summarize", context="", at=_AT))
    backend = TextBackend(["sum", "mary"])
    result = await _runner(store, backend).run("t1")
    assert (result.task_id, result.ok, result.output) == ("t1", True, "summary")
    assert result.tainted is False
    assert await store.get_result("t1") == result
    (messages,) = backend.seen
    assert [m.role for m in messages] == [Role.USER]
    assert messages[0].text == "summarize"


async def test_reasoning_deltas_are_dropped_from_the_subagent_output() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="add", context="", at=_AT))
    backend = ScriptedBackend([[ReasoningChunk("thinking..."), TextChunk("42")]])
    result = await _runner(store, backend).run("t1")
    assert (result.ok, result.output) == (True, "42")


async def test_context_is_passed_as_a_system_message() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t2", instruction="do", context="the context", at=_AT))
    backend = TextBackend(["ok"])
    await _runner(store, backend).run("t2")
    (messages,) = backend.seen
    assert [m.role for m in messages] == [Role.SYSTEM, Role.USER]
    assert (messages[0].text, messages[1].text) == ("the context", "do")


async def test_missing_task_becomes_a_failed_result() -> None:
    store = InMemoryTaskStore()
    result = await _runner(store, TextBackend(["x"])).run("ghost")
    assert (result.ok, result.detail, result.output) == (False, "task not found", "")
    assert await store.get_result("ghost") == result


async def test_inference_failure_becomes_a_failed_result_with_partial_text() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t3", instruction="go", context="", at=_AT))
    result = await _runner(store, FailingBackend()).run("t3")
    assert result.ok is False
    assert result.output == "partial "
    assert "backend exploded" in result.detail
    assert await store.get_result("t3") == result


async def test_tools_enabled_subagent_dispatches_and_audits_its_calls() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t4", instruction="read x", context="", at=_AT))
    backend = ScriptedBackend(
        [
            [TextChunk("looking... "), ToolCall(id="c1", name="read", arguments={"path": "/x"})],
            [TextChunk("done")],
        ]
    )
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    dispatcher = ToolDispatcher(registry, sink, FixedClock())
    result = await _runner(store, backend, tools=dispatcher).run("t4")
    assert result.ok is True
    assert result.output == "looking... done"
    assert result.tainted is True
    (audit,) = sink.records
    assert (audit.name, audit.ok, audit.detail) == ("read", True, "read /x")


_DESCRIBED_READ = ToolSpec(name="read", description="Read a file", parameters={})


async def test_a_tools_enabled_subagents_tool_steps_reach_the_progress_sink() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="read x", context="", at=_AT))
    backend = ScriptedBackend(
        [
            [ToolCall(id="c1", name="read", arguments={"path": "/x"})],
            [TextChunk("done")],
        ]
    )
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"read": (_DESCRIBED_READ, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    progress = RecordingProgressSink()
    result = await _runner(store, backend, tools=dispatcher).run("t", progress=progress)
    assert result.ok is True
    assert list(progress.events) == [ToolActivity(tool_name="read", summary="Read a file")]


async def test_a_tainted_subagents_progress_carries_only_the_registry_summary() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="read x", context="", at=_AT))
    backend = ScriptedBackend(
        [
            [ToolCall(id="c1", name="read", arguments={"path": "/secret"})],
            [TextChunk("done")],
        ]
    )
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"read": (_DESCRIBED_READ, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    progress = RecordingProgressSink()
    result = await _runner(store, backend, tools=dispatcher).run("t", progress=progress)
    assert result.tainted is True
    (step,) = progress.events
    assert isinstance(step, ToolActivity)
    assert step == ToolActivity(tool_name="read", summary="Read a file")
    assert "secret" not in step.summary


async def test_a_tool_less_subagent_emits_no_progress_even_with_a_sink() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT))
    progress = RecordingProgressSink()
    result = await _runner(store, TextBackend(["plain"])).run("t", progress=progress)
    assert (result.ok, result.output) == (True, "plain")
    assert progress.events == ()


def _reading_runner(
    store: InMemoryTaskStore, backend: InferenceBackend, sink: RecordingAuditSink
) -> SubagentRunner:
    """A runner with one ``read`` tool, sharing the caller's audit sink."""
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    return _runner(store, backend, tools=ToolDispatcher(registry, sink, FixedClock()))


def _two_call_backend() -> ScriptedBackend:
    """Two rounds of one tool call each, then a final answer."""
    return ScriptedBackend(
        [
            [ToolCall(id="c1", name="read", arguments={"path": "/x"})],
            [ToolCall(id="c2", name="read", arguments={"path": "/y"})],
            [TextChunk("done")],
        ]
    )


async def test_a_handed_budget_is_what_the_subagents_dispatches_come_out_of() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t9", instruction="read x", context="", at=_AT))
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=1)
    result = await _reading_runner(store, _two_call_backend(), sink).run("t9", budget=pool)
    assert result.ok is True
    assert pool.spent == 1
    assert [record.ok for record in sink.records] == [True, False]
    assert sink.records[1].detail == BUDGET_EXHAUSTED_MSG


async def test_a_run_with_no_spawning_turn_gets_its_own_allowance() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="rooted", instruction="read x", context="", at=_AT))
    await store.put_task(SubagentTask(id="starved", instruction="read x", context="", at=_AT))
    sink = RecordingAuditSink()
    await _reading_runner(store, _two_call_backend(), sink).run("rooted")
    dispatched_by_the_root = [record.ok for record in sink.records]
    starved = _reading_runner(store, _two_call_backend(), sink)
    await starved.run("starved", budget=DispatchBudget(limit=0))
    assert dispatched_by_the_root == [True, True]
    assert [record.ok for record in sink.records[2:]] == [False, False]


_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


async def test_constrained_tool_less_subagent_passes_the_envelope_and_unwraps_the_reply() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="name a color", context="", at=_AT))
    backend = SchemaRecordingBackend(['{"reply": "blue', '"}'])
    result = await _runner(store, backend, constrain_output=True).run("t1")
    assert (result.ok, result.output) == (True, "blue")
    assert backend.schemas == [_ENVELOPE]


def _user_text(backend: SchemaRecordingBackend) -> str:
    """The text of the single user message in the first call."""
    return next(m.text for m in backend.asked[0] if m.role is Role.USER)


async def test_a_constrained_ask_carries_the_envelopes_own_sentence_on_the_instruction() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="name a color", context="", at=_AT))
    backend = SchemaRecordingBackend(['{"reply": "blue"}'])
    await _runner(store, backend, constrain_output=True).run("t1")
    assert _user_text(backend) == f"name a color {REPLY_INSTRUCTION}"


async def test_an_unconstrained_ask_carries_the_instruction_and_nothing_else() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="name a color", context="", at=_AT))
    backend = SchemaRecordingBackend(["blue"])
    await _runner(store, backend, constrain_output=False).run("t1")
    assert _user_text(backend) == "name a color"


async def test_a_tools_enabled_subagent_is_asked_without_the_sentence_too() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="name a color", context="", at=_AT))
    backend = SchemaRecordingBackend(["blue"])
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), FixedClock())
    await _runner(store, backend, tools=dispatcher, constrain_output=True).run("t1")
    assert _user_text(backend) == "name a color"


async def test_a_malformed_constrained_reply_is_a_failed_result_carrying_the_raw_text() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["not a JSON envelope"])
    result = await _runner(store, backend, constrain_output=True).run("t1")
    assert result.ok is False
    assert result.output == "not a JSON envelope"
    assert "malformed" in result.detail


async def test_a_constrained_reply_missing_the_key_is_a_failed_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    result = await _runner(
        store, SchemaRecordingBackend(['{"other": 1}']), constrain_output=True
    ).run("t1")
    assert result.ok is False
    assert "malformed" in result.detail


async def test_output_is_unconstrained_when_the_setting_is_off() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["plain answer"])
    result = await _runner(store, backend, constrain_output=False).run("t1")
    assert (result.ok, result.output) == (True, "plain answer")
    assert backend.schemas == [None]


async def test_a_tools_enabled_subagent_is_never_constrained() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["ok"])
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), FixedClock())
    result = await _runner(store, backend, tools=dispatcher, constrain_output=True).run("t1")
    assert (result.ok, result.output) == (True, "ok")
    assert backend.schemas == [None]


def _routed_runner(
    store: InMemoryTaskStore, gpu: InferenceBackend, cpu: InferenceBackend, placer: SubagentPlacer
) -> SubagentRunner:
    return SubagentRunner(store, _roster(_resources(gpu, cpu, placer)), FixedClock())


async def test_a_fitting_subagent_runs_on_the_gpu_backend_and_its_vram_is_released() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="hi", context="", at=_AT))
    gpu, cpu = TextBackend(["on-gpu"]), TextBackend(["on-cpu"])
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)  # 3.0 GiB headroom
    result = await _routed_runner(store, gpu, cpu, placer).run("g")
    assert result.output == "on-gpu"
    assert gpu.seen
    assert not cpu.seen
    assert placer.place(PlacementRequest("subagent", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


async def test_an_overflowing_subagent_runs_on_the_cpu_backend() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="c", instruction="hi", context="", at=_AT))
    gpu, cpu = TextBackend(["on-gpu"]), TextBackend(["on-cpu"])
    placer = VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0)  # no headroom
    result = await _routed_runner(store, gpu, cpu, placer).run("c")
    assert result.output == "on-cpu"
    assert cpu.seen
    assert not gpu.seen


def _refusal_line(caplog: pytest.LogCaptureFixture) -> str:
    """The one refusal warning the runner logged, rendered the way an operator sees it."""
    (record,) = [line for line in caplog.records if line.name == _RUNNER_LOGGER]
    return PlainFormatter().format(record)


async def test_a_spawn_the_scheduler_refuses_becomes_a_result_not_an_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="do", context="", at=_AT))
    backend = TextBackend(["never runs"])
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=placer,
        request=PlacementRequest("subagent", vram_gb=2.0, cpus=8.0, memory_gb=2.0),
    )
    with caplog.at_level(logging.WARNING, logger=_RUNNER_LOGGER):
        result = await SubagentRunner(store, _roster(resources), FixedClock()).run("t1")
    assert (result.ok, result.output) == (False, "")
    assert "refused before running" in result.detail
    assert "exceeds the whole budget" in result.detail
    line = _refusal_line(caplog)
    assert line.startswith(f"WARNING:{_RUNNER_LOGGER}:a spawn was refused before it ran ")
    assert " model=subagent " in line
    assert " task_id=t1" in line
    assert "exceeds the whole budget" in line
    assert not backend.seen
    assert await store.get_result("t1") == result
    assert placer.place(PlacementRequest("subagent", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


@asynccontextmanager
async def _peer_holding_the_whole_budget(
    scheduler: ResourceBudgetScheduler,
) -> AsyncGenerator[None]:
    """Hold the whole budget in another task for the block, so any spawn has to queue."""
    holding, release = asyncio.Event(), asyncio.Event()

    async def peer() -> None:
        async with scheduler.admit(PlacementRequest("peer", vram_gb=1.0, cpus=4.0, memory_gb=8.0)):
            holding.set()
            await release.wait()

    task = asyncio.create_task(peer())
    await holding.wait()
    try:
        yield
    finally:
        release.set()
        await task


async def test_a_spawn_that_waits_out_the_admission_bound_is_a_result_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="do", context="", at=_AT))
    backend = TextBackend(["never runs"])
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=scheduler,
        placer=placer,
        request=_REQUEST,
    )
    runner = SubagentRunner(store, _roster(resources), FixedClock())
    with caplog.at_level(logging.WARNING, logger=_RUNNER_LOGGER):
        async with asyncio.timeout(10.0), _peer_holding_the_whole_budget(scheduler):
            result = await runner.run("t1")
    assert (result.ok, result.output) == (False, "")
    assert "refused before running" in result.detail
    assert "outlasts the deployment's admission bound" in result.detail
    assert "outlasts the deployment's admission bound" in _refusal_line(caplog)
    assert not backend.seen
    assert await store.get_result("t1") == result
    assert placer.place(PlacementRequest("subagent", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


def _two_model_runner(
    store: InMemoryTaskStore,
    default_backend: InferenceBackend,
    fast: InferenceBackend,
    *,
    tools: ToolDispatcher | None = None,
) -> SubagentRunner:
    """A roster with the ``subagent`` default plus a ``fast`` alternate, each on its own backend."""
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    roster = SubagentRoster(
        entries={
            "subagent": SubagentProfile(
                resources=_resources(default_backend, default_backend, placer)
            ),
            "fast": SubagentProfile(
                resources=SubagentResources(
                    backends={PlacementTarget.GPU: fast, PlacementTarget.CPU: fast},
                    scheduler=ResourceBudgetScheduler(4.0, 8.0),
                    placer=placer,
                    request=PlacementRequest("fast", vram_gb=1.0, cpus=1.0, memory_gb=1.0),
                )
            ),
        },
        default="subagent",
    )
    return SubagentRunner(store, roster, FixedClock(), tools=tools)


async def test_a_clean_tool_less_spawn_runs_on_the_requested_model() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT, model="fast"))
    default_backend, fast = TextBackend(["default says"]), TextBackend(["fast says"])
    result = await _two_model_runner(store, default_backend, fast).run("t")
    assert result.output == "fast says"
    assert fast.seen
    assert not default_backend.seen


async def test_a_tainted_spawn_is_forced_onto_the_default_model() -> None:
    store = InMemoryTaskStore()
    await store.put_task(
        SubagentTask(id="t", instruction="go", context="", at=_AT, model="fast", tainted=True)
    )
    default_backend, fast = TextBackend(["default says"]), TextBackend(["fast says"])
    result = await _two_model_runner(store, default_backend, fast).run("t")
    assert result.output == "default says"
    assert default_backend.seen
    assert not fast.seen


async def test_a_tools_enabled_spawn_is_forced_onto_the_default_model() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT, model="fast"))
    default_backend, fast = TextBackend(["default says"]), TextBackend(["fast says"])
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    result = await _two_model_runner(store, default_backend, fast, tools=dispatcher).run("t")
    assert result.output == "default says"
    assert default_backend.seen
    assert not fast.seen


async def test_an_unknown_model_fails_closed_as_a_failed_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT, model="ghost"))
    backend = TextBackend(["never"])
    result = await _runner(store, backend).run("t")
    assert (result.ok, result.output) == (False, "")
    assert "unknown subagent model 'ghost'" in result.detail
    assert not backend.seen
    assert await store.get_result("t") == result


async def test_the_runner_exposes_its_roster_and_tool_enablement() -> None:
    store = InMemoryTaskStore()
    runner = _runner(store, TextBackend(["x"]))
    assert runner.roster.default == "subagent"
    assert runner.tools_enabled is False
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    assert _runner(store, TextBackend(["x"]), tools=dispatcher).tools_enabled is True


class CountingFailure:
    """Fails every call with the typed inference error and counts how often it was asked."""

    def __init__(self, reason: str) -> None:
        self.calls = 0
        self._reason = reason

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        self.calls += 1
        yield TextChunk("partial ")
        raise InferenceError(self._reason)


class ToolThenFailBackend:
    """Dispatches one tool call, then fails on the next round."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        self.calls += 1
        if self.calls == 1:
            yield ToolCall(id="c1", name="read", arguments={"path": "/x"})
            return
        msg = "the gpu stream died"
        raise InferenceError(msg)


class HeadroomProbingBackend:
    """Answers, and records the headroom the placer had while it answered."""

    def __init__(self, placer: SubagentPlacer) -> None:
        self._placer = placer
        self.probes: list[PlacementTarget] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        probe = self._placer.place(PlacementRequest("probe", vram_gb=3.0, cpus=1.0, memory_gb=1.0))
        self.probes.append(probe.target)
        self._placer.release(probe)
        yield TextChunk("on-cpu")


def _gpu_placer() -> VramBudgetPlacer:
    """3.0 GiB of headroom against the 2.0 GiB request, so every subagent fits the GPU."""
    return VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)


async def test_a_gpu_placed_backend_that_did_not_answer_is_re_run_once_on_the_cpu() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="hi", context="", at=_AT))
    gpu, cpu = CountingFailure("the gpu server is down"), TextBackend(["on-cpu"])
    result = await _routed_runner(store, gpu, cpu, _gpu_placer()).run("g")
    assert (result.ok, result.output) == (True, "on-cpu")
    assert (gpu.calls, len(cpu.seen)) == (1, 1)
    assert result.detail == (
        "the GPU attempt failed (the gpu server is down); re-ran on the CPU, which answered"
    )
    assert await store.get_result("g") == result


async def test_the_cpu_re_run_happens_exactly_once_and_both_failures_are_recorded() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="hi", context="", at=_AT))
    backend = CountingFailure("nothing is serving")
    runner = SubagentRunner(
        store, _roster(_resources(backend, backend, _gpu_placer())), FixedClock()
    )
    result = await runner.run("g")
    assert backend.calls == ATTEMPTS_PER_ADMISSION == 2
    assert result.ok is False
    assert result.output == "partial "
    assert result.detail == (
        "the GPU attempt failed (nothing is serving); the CPU re-run failed too "
        "(nothing is serving)"
    )


async def test_a_cpu_placed_failure_is_not_re_run_because_there_is_nowhere_better() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="c", instruction="hi", context="", at=_AT))
    gpu, cpu = TextBackend(["on-gpu"]), CountingFailure("the cpu server is down")
    placer = VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0)  # no headroom
    result = await _routed_runner(store, gpu, cpu, placer).run("c")
    assert (cpu.calls, gpu.seen) == (1, [])
    assert result.ok is False
    assert result.detail == "the cpu server is down"


async def test_a_malformed_constrained_reply_is_not_re_placed() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="m", instruction="go", context="", at=_AT))
    backend = TextBackend(["not json at all"])
    result = await _runner(store, backend, constrain_output=True).run("m")
    assert len(backend.seen) == 1
    assert result.ok is False
    assert result.detail == "subagent produced a malformed constrained reply"


async def test_the_gpu_reservation_is_released_before_the_cpu_re_run() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="hi", context="", at=_AT))
    placer = _gpu_placer()
    cpu = HeadroomProbingBackend(placer)
    result = await _routed_runner(store, CountingFailure("gone"), cpu, placer).run("g")
    assert result.output == "on-cpu"
    assert cpu.probes == [PlacementTarget.GPU]


async def test_the_taint_a_failed_gpu_attempt_read_survives_into_the_re_run_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="read x", context="", at=_AT))
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"read": (_DESCRIBED_READ, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    gpu, cpu = ToolThenFailBackend(), TextBackend(["clean answer"])
    runner = SubagentRunner(
        store, _roster(_resources(gpu, cpu, _gpu_placer())), FixedClock(), tools=dispatcher
    )
    result = await runner.run("g")
    assert (result.ok, result.output) == (True, "clean answer")
    assert result.tainted is True


async def test_both_attempts_spend_from_the_spawning_turns_one_pool() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="read x", context="", at=_AT))
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"read": (_DESCRIBED_READ, _read_handler)}),
        RecordingAuditSink(),
        FixedClock(),
    )
    gpu = ToolThenFailBackend()
    cpu = ScriptedBackend(
        [[ToolCall(id="c2", name="read", arguments={"path": "/y"})], [TextChunk("done")]]
    )
    runner = SubagentRunner(
        store, _roster(_resources(gpu, cpu, _gpu_placer())), FixedClock(), tools=dispatcher
    )
    budget = DispatchBudget()
    result = await runner.run("g", budget=budget)
    assert result.output == "done"
    assert budget.spent == 2
