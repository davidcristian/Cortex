"""Behavior tests for SubagentRunner: a stateless function over the TaskStore (ADR-0010/0018)."""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    BUDGET_EXHAUSTED_MSG,
    DispatchBudget,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
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

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    """A clock pinned to one instant. The runner only needs it to stamp tool messages."""

    def now(self) -> datetime:
        return _AT


class TextBackend:
    """Yields fixed text deltas and records the messages it was handed."""

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


class ScriptedBackend:
    """Replays a per-step list of events (text deltas and/or tool calls)."""

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
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
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
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
        yield TextChunk("partial ")
        msg = "backend exploded"
        raise InferenceError(msg)


class SchemaRecordingBackend:
    """Records the schema it was handed each call and yields fixed text (ADR-0028)."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas
        self.schemas: list[JsonSchema | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        self.schemas.append(schema)
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
    # Both targets route to the one backend; the placer picks GPU (headroom 14 - 11 = 3 >= 2).
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
    assert result.tainted is False  # a tool-less subagent reads no untrusted content
    # The cortex reads the outcome back from the store, not from the runner's return.
    assert await store.get_result("t1") == result
    # No context -> a single user message carrying the instruction.
    (messages,) = backend.seen
    assert [m.role for m in messages] == [Role.USER]
    assert messages[0].text == "summarize"


async def test_reasoning_deltas_are_dropped_from_the_subagent_output() -> None:
    """A reasoning delta (ADR-0020) is ephemeral status, not the answer: the subagent tier runs
    thinking-off, but the runner drops any reasoning defensively rather than folding it in."""
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
    assert result.output == "partial "  # text produced before the failure is kept
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
    assert result.tainted is True  # it read an untrusted tool result -> the result is tainted
    # The subagent's own tool call went through the same audited dispatcher.
    (audit,) = sink.records
    assert (audit.name, audit.ok, audit.detail) == ("read", True, "read /x")


_DESCRIBED_READ = ToolSpec(name="read", description="Read a file", parameters={})


async def test_a_tools_enabled_subagents_tool_steps_reach_the_progress_sink() -> None:
    # Each audited step the subagent runs surfaces onto the spawning stream's sink as a
    # ToolActivity (ADR-0010 progress addendum), so the overlay's chip shows the delegated
    # work. Both fields are the matched ToolSpec's, never the model's call or its arguments.
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
    # The read tool returns UNTRUSTED content, so the result taints, but the surfaced step is the
    # spec's own name/description, never the untrusted bytes: the sink is not a laundering channel
    # the ADR-0015 guardrail never inspects, the exact argument the cortex's ToolActivity makes.
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
    assert result.tainted is True  # it consumed untrusted content
    (step,) = progress.events
    assert isinstance(step, ToolActivity)
    assert step == ToolActivity(tool_name="read", summary="Read a file")
    assert "secret" not in step.summary  # the untrusted result never reached the chip


async def test_a_tool_less_subagent_emits_no_progress_even_with_a_sink() -> None:
    # A tool-less subagent yields no ToolStep, so a handed sink stays empty: only real audited
    # steps surface, never the reply text or a phantom activity.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT))
    progress = RecordingProgressSink()
    result = await _runner(store, TextBackend(["plain"])).run("t", progress=progress)
    assert (result.ok, result.output) == (True, "plain")
    assert progress.events == ()


def _reading_runner(
    store: InMemoryTaskStore, backend: InferenceBackend, sink: RecordingAuditSink
) -> SubagentRunner:
    """A tools-enabled runner over one `read` tool, sharing the caller's audit sink."""
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
    # The turn-wide property at the runner (ADR-0009 turn-wide addendum): a subagent spawned by
    # a cortex turn spends that turn's pool, so its calls stop when the turn's allowance does
    # rather than when a private count of its own would have.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t9", instruction="read x", context="", at=_AT))
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=1)
    result = await _reading_runner(store, _two_call_backend(), sink).run("t9", budget=pool)
    assert result.ok is True
    assert pool.spent == 1  # charged against the caller's pool, not a private one
    assert [record.ok for record in sink.records] == [True, False]
    assert sink.records[1].detail == BUDGET_EXHAUSTED_MSG


async def test_a_run_with_no_spawning_turn_gets_its_own_allowance() -> None:
    # The ticker's fire (ADR-0025) dispatches spawn_subagents directly, outside any tool loop,
    # so its stamp carries no pool. That run is its own root and must still be able to dispatch,
    # while a run handed an exhausted pool must not: both branches of the same fallback.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="rooted", instruction="read x", context="", at=_AT))
    await store.put_task(SubagentTask(id="starved", instruction="read x", context="", at=_AT))
    sink = RecordingAuditSink()
    await _reading_runner(store, _two_call_backend(), sink).run("rooted")
    dispatched_by_the_root = [record.ok for record in sink.records]
    starved = _reading_runner(store, _two_call_backend(), sink)
    await starved.run("starved", budget=DispatchBudget(limit=0))
    assert dispatched_by_the_root == [True, True]  # its own allowance covered both calls
    assert [record.ok for record in sink.records[2:]] == [False, False]


_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


async def test_constrained_tool_less_subagent_passes_the_envelope_and_unwraps_the_reply() -> None:
    # ADR-0028: a tool-less subagent with constrain_output on gets the fixed envelope schema, and
    # the runner unwraps the reply so the cortex sees an answer, never raw JSON.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="name a color", context="", at=_AT))
    backend = SchemaRecordingBackend(['{"reply": "blue', '"}'])
    result = await _runner(store, backend, constrain_output=True).run("t1")
    assert (result.ok, result.output) == (True, "blue")
    assert backend.schemas == [_ENVELOPE]  # the envelope was threaded to the backend


async def test_a_malformed_constrained_reply_is_a_failed_result_carrying_the_raw_text() -> None:
    # A weak model that slips the grammar (or a partial stream) degrades to ok=False, and the
    # raw payload rides as the output for debugging rather than being persisted as the answer.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["not a JSON envelope"])
    result = await _runner(store, backend, constrain_output=True).run("t1")
    assert result.ok is False
    assert result.output == "not a JSON envelope"
    assert "malformed" in result.detail


async def test_a_constrained_reply_missing_the_key_is_a_failed_result() -> None:
    # Valid JSON but the wrong shape (no string ``reply``) is also malformed.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    result = await _runner(
        store, SchemaRecordingBackend(['{"other": 1}']), constrain_output=True
    ).run("t1")
    assert result.ok is False
    assert "malformed" in result.detail


async def test_output_is_unconstrained_when_the_knob_is_off() -> None:
    # With constrain_output off, the tool-less path gets no schema and the raw text is the answer.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["plain answer"])
    result = await _runner(store, backend, constrain_output=False).run("t1")
    assert (result.ok, result.output) == (True, "plain answer")
    assert backend.schemas == [None]


async def test_a_tools_enabled_subagent_is_never_constrained() -> None:
    # The constraint is gated to the tool-less path (ADR-0028 decision 3): a tools-enabled
    # subagent gets no schema even with the knob on, so the JSON envelope never fights the
    # tool-calling grammar.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="go", context="", at=_AT))
    backend = SchemaRecordingBackend(["ok"])
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), FixedClock())
    result = await _runner(store, backend, tools=dispatcher, constrain_output=True).run("t1")
    assert (result.ok, result.output) == (True, "ok")
    assert backend.schemas == [None]  # tool-enabled -> unconstrained


def _routed_runner(
    store: InMemoryTaskStore, gpu: InferenceBackend, cpu: InferenceBackend, placer: SubagentPlacer
) -> SubagentRunner:
    return SubagentRunner(store, _roster(_resources(gpu, cpu, placer)), FixedClock())


async def test_a_fitting_subagent_runs_on_the_gpu_backend_and_its_vram_is_released() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="g", instruction="hi", context="", at=_AT))
    gpu, cpu = TextBackend(["on-gpu"]), TextBackend(["on-cpu"])
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)  # headroom 3.0
    result = await _routed_runner(store, gpu, cpu, placer).run("g")
    assert result.output == "on-gpu"
    assert gpu.seen
    assert not cpu.seen
    # The placement's 2 GB was released in the finally, so the whole 3 GB headroom is free again.
    assert placer.place(PlacementRequest("subagent", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


async def test_an_overflowing_subagent_runs_on_the_cpu_backend() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="c", instruction="hi", context="", at=_AT))
    gpu, cpu = TextBackend(["on-gpu"]), TextBackend(["on-cpu"])
    placer = VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0)  # headroom 0.0
    result = await _routed_runner(store, gpu, cpu, placer).run("c")
    assert result.output == "on-cpu"
    assert cpu.seen
    assert not gpu.seen


async def test_a_spawn_the_scheduler_refuses_becomes_a_result_not_an_exception() -> None:
    """The budget's wall reaches the cortex as a value (ADR-0012 admission-wall addendum).

    An escaping exception would cross `SpawnSubagentsTool`, past which only `ToolError` is
    caught, and fail the whole turn. The runner's contract is that every outcome is a persisted
    `SubagentResult`, so the refusal joins "task not found" and "unknown subagent model".
    """
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t1", instruction="do", context="", at=_AT))
    backend = TextBackend(["never runs"])
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)  # headroom 3.0
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=placer,
        # 8 cpus against a whole budget of 4: no peer releasing anything could ever admit it.
        request=PlacementRequest("subagent", vram_gb=2.0, cpus=8.0, memory_gb=2.0),
    )
    result = await SubagentRunner(store, _roster(resources), FixedClock()).run("t1")
    assert (result.ok, result.output) == (False, "")
    assert "refused before running" in result.detail
    assert "exceeds the whole budget" in result.detail
    assert not backend.seen  # refused before running means no inference was ever issued
    assert await store.get_result("t1") == result  # the cortex reads it back from the store
    # Placement is inside admission, so a refusal reserved no VRAM either: headroom is intact.
    assert placer.place(PlacementRequest("subagent", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


def _two_model_runner(
    store: InMemoryTaskStore,
    robust: InferenceBackend,
    fast: InferenceBackend,
    *,
    tools: ToolDispatcher | None = None,
) -> SubagentRunner:
    """A roster with the robust default plus a 'fast' alternate, each on its own backend."""
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    roster = SubagentRoster(
        entries={
            "subagent": SubagentProfile(resources=_resources(robust, robust, placer)),
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
    robust, fast = TextBackend(["robust says"]), TextBackend(["fast says"])
    result = await _two_model_runner(store, robust, fast).run("t")
    assert result.output == "fast says"
    assert fast.seen
    assert not robust.seen


async def test_a_tainted_spawn_is_forced_onto_the_robust_default() -> None:
    # ADR-0017 rule 2a: the spawning turn read untrusted content, so the requested cheap
    # model is overridden. The instruction itself may be hostile.
    store = InMemoryTaskStore()
    await store.put_task(
        SubagentTask(id="t", instruction="go", context="", at=_AT, model="fast", tainted=True)
    )
    robust, fast = TextBackend(["robust says"]), TextBackend(["fast says"])
    result = await _two_model_runner(store, robust, fast).run("t")
    assert result.output == "robust says"
    assert robust.seen
    assert not fast.seen


async def test_a_tools_enabled_spawn_is_forced_onto_the_robust_default() -> None:
    # ADR-0017 rule 2b: a tools-enabled subagent can fetch untrusted content itself, so the
    # model choice is pinned regardless of the turn's taint.
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT, model="fast"))
    robust, fast = TextBackend(["robust says"]), TextBackend(["fast says"])
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    result = await _two_model_runner(store, robust, fast, tools=dispatcher).run("t")
    assert result.output == "robust says"
    assert robust.seen
    assert not fast.seen


async def test_an_unknown_model_fails_closed_as_a_failed_result() -> None:
    store = InMemoryTaskStore()
    await store.put_task(SubagentTask(id="t", instruction="go", context="", at=_AT, model="ghost"))
    backend = TextBackend(["never"])
    result = await _runner(store, backend).run("t")
    assert (result.ok, result.output) == (False, "")
    assert "unknown subagent model 'ghost'" in result.detail
    assert not backend.seen  # nothing was admitted, placed, or run
    assert await store.get_result("t") == result


async def test_the_runner_exposes_its_roster_and_tool_enablement() -> None:
    # The spawn tool advertises from these (ADR-0018), so they must reflect the wiring.
    store = InMemoryTaskStore()
    runner = _runner(store, TextBackend(["x"]))
    assert runner.roster.default == "subagent"
    assert runner.tools_enabled is False
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    assert _runner(store, TextBackend(["x"]), tools=dispatcher).tools_enabled is True
