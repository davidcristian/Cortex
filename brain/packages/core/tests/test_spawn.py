"""Behavior tests for the spawn_subagents built-in tool (ADR-0010/0018)."""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from cortex_core import (
    BUDGET_EXHAUSTED_MSG,
    MAX_SPAWN_BATCH,
    SUBAGENT_PROGRESS_STATE,
    DispatchBudget,
    EchoInferenceBackend,
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
    ProgressSink,
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
    TurnStamp,
    VramBudgetPlacer,
)

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _AT


class FailingBackend:
    """Yields one delta then fails. Every subagent driven by it comes back ok=False."""

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
        yield TextChunk("x")
        msg = "boom"
        raise InferenceError(msg)


def _counter() -> Callable[[], str]:
    ids = iter(f"st-{n}" for n in range(1, 1000))
    return lambda: next(ids)


def _profile(backend: InferenceBackend, model: str, description: str = "") -> SubagentProfile:
    return SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
            scheduler=ResourceBudgetScheduler(8.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
        ),
        description=description,
    )


def _runner(
    store: InMemoryTaskStore,
    backend: InferenceBackend,
    model: str,
    *,
    tools: ToolDispatcher | None = None,
) -> SubagentRunner:
    roster = SubagentRoster(entries={model: _profile(backend, model)}, default=model)
    return SubagentRunner(store, roster, FixedClock(), tools=tools)


def _tool(store: InMemoryTaskStore, backend: InferenceBackend) -> SpawnSubagentsTool:
    return SpawnSubagentsTool(
        _runner(store, backend, "subagent"), store, FixedClock(), task_id_factory=_counter()
    )


def _call(
    arguments: dict[str, object],
    *,
    tainted: bool = False,
    budget: DispatchBudget | None = None,
    progress: ProgressSink | None = None,
) -> ToolCall:
    stamp = TurnStamp(tainted=tainted, budget=budget, progress=progress)
    return ToolCall(id="c1", name="spawn_subagents", arguments=arguments, stamp=stamp)


class OneToolCallBackend:
    """Calls one tool on a subagent's first round, then answers. Stateless, so the whole batch
    can share one instance and each concurrent run drives it independently: whether a round is
    the first is read off the messages (a tool result present means the call already happened)
    rather than off a counter that concurrency would scramble.
    """

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


def _delegating_tool(
    store: InMemoryTaskStore, sink: RecordingAuditSink
) -> tuple[SpawnSubagentsTool, SubagentRunner]:
    """A spawn tool whose subagents hold one `read` tool, all auditing to ``sink``."""
    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="", parameters={}), _read_handler)}
    )
    runner = _runner(
        store,
        OneToolCallBackend(),
        "subagent",
        tools=ToolDispatcher(registry, sink, FixedClock()),
    )
    return SpawnSubagentsTool(runner, store, FixedClock(), task_id_factory=_counter()), runner


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"read {arguments['path']}"


async def test_a_batch_shares_the_spawning_turns_pool_instead_of_one_each() -> None:
    # The hole this closes (ADR-0009 turn-wide addendum): every subagent used to start a fresh
    # budget, so an unbounded `instructions` array bought an unbounded number of external calls
    # for the price of one spawn. Three subagents each wanting one dispatch, two units left in
    # the turn's pool: two calls reach the outside world, not three.
    store = InMemoryTaskStore()
    sink = RecordingAuditSink()
    tool, _ = _delegating_tool(store, sink)
    pool = DispatchBudget(limit=2)
    result = await tool.invoke(_call({"instructions": ["a", "b", "c"]}, budget=pool))
    assert result.is_error is False
    assert pool.spent == 2
    assert len([record for record in sink.records if record.ok]) == 2
    refused = [record for record in sink.records if not record.ok]
    assert [record.detail for record in refused] == [BUDGET_EXHAUSTED_MSG]


async def test_a_spawn_with_no_pool_on_its_stamp_leaves_each_subagent_its_own() -> None:
    # The schedule ticker (ADR-0025) dispatches spawn_subagents directly, outside any tool loop,
    # so its stamp carries no pool. Every subagent then runs on its own allowance, exactly as
    # before this addendum: a fire is its own root, like a turn.
    store = InMemoryTaskStore()
    sink = RecordingAuditSink()
    tool, _ = _delegating_tool(store, sink)
    result = await tool.invoke(_call({"instructions": ["a", "b", "c"]}))
    assert result.is_error is False
    assert [record.ok for record in sink.records] == [True, True, True]


async def test_spawns_run_concurrently_and_results_aggregate_in_order() -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, EchoInferenceBackend()).invoke(
        _call({"instructions": ["do A", "do B"]})
    )
    assert result.is_error is False
    assert result.content == "[subagent 1] reply 1: do A\n\n[subagent 2] reply 1: do B"
    # Each subtask was persisted to the store (the runner read it back by id).
    first, second = await store.get_task("st-1"), await store.get_task("st-2")
    assert first is not None
    assert second is not None
    assert (first.instruction, second.instruction) == ("do A", "do B")
    # A bare string requests the default model, no context, and rides the clean-turn stamp.
    assert (first.model, first.context, first.tainted) == ("", "", False)


async def test_default_task_id_factory_round_trips_through_the_store() -> None:
    # With no injected factory the tool mints uuid4 task ids; the subagent's success proves the
    # same id was used to persist and to read the task back (a mismatch would be "task not found").
    store = InMemoryTaskStore()
    tool = SpawnSubagentsTool(_runner(store, EchoInferenceBackend(), "s"), store, FixedClock())
    result = await tool.invoke(_call({"instructions": ["go"]}))
    assert result.content == "[subagent 1] reply 1: go"


async def test_a_failed_subagent_is_reported_not_raised() -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, FailingBackend()).invoke(_call({"instructions": ["go"]}))
    assert result.is_error is False  # the tool ran; the subagent's failure is content
    # This harness places on the GPU and serves both targets from the one backend, so the runner's
    # single CPU re-run (ADR-0012's re-place) fires and fails too, and the detail it records is
    # what the cortex reads back. Two attempts of one subtask is the honest thing to tell it.
    assert result.content == (
        "[subagent 1] FAILED: the GPU attempt failed (boom); the CPU re-run failed too (boom)"
    )


async def test_a_refused_subagent_does_not_take_the_rest_of_the_batch_down() -> None:
    """The scheduler's wall is one member's outcome, never the batch's (ADR-0012 addendum).

    `asyncio.gather` propagates the first exception, so a refusal that stayed an exception would
    lose every sibling's answer and fail the turn. As a value it is one `FAILED:` section.
    """
    store = InMemoryTaskStore()
    backend = EchoInferenceBackend()
    oversized = SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
            scheduler=ResourceBudgetScheduler(8.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            # 16 cpus against a whole budget of 8: refused on every attempt, never queued.
            request=PlacementRequest("toobig", vram_gb=2.0, cpus=16.0, memory_gb=2.0),
        )
    )
    roster = SubagentRoster(
        entries={"subagent": _profile(backend, "subagent"), "toobig": oversized},
        default="subagent",
    )
    tool = SpawnSubagentsTool(
        SubagentRunner(store, roster, FixedClock()), store, FixedClock(), task_id_factory=_counter()
    )
    result = await tool.invoke(
        _call({"instructions": [{"instruction": "go", "model": "toobig"}, "stay"]})
    )
    assert result.is_error is False
    first, second = result.content.split("\n\n")
    assert first.startswith("[subagent 1] FAILED: refused before running: subagent charge")
    assert second == "[subagent 2] reply 1: stay"


async def test_a_delegating_batch_surfaces_its_scale_and_the_subagents_tool_steps() -> None:
    # The two halves of the side channel (ADR-0010 progress addendum) over one call: a batch-start
    # StatusUpdate carrying the brain-authored subtask count, then a ToolActivity per subagent's
    # audited tool step. Both ride the sink off the call stamp while the cortex loop is suspended
    # in this dispatch.
    store = InMemoryTaskStore()
    audit = RecordingAuditSink()
    tool, _ = _delegating_tool(store, audit)
    progress = RecordingProgressSink()
    result = await tool.invoke(_call({"instructions": ["a", "b"]}, progress=progress))
    assert result.is_error is False
    events = progress.events
    # The scale comes first, deterministically (emitted before the batch's gather):
    assert events[0] == StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail="delegating 2 subtasks")
    # Then a `read` step per subagent, both registry-authored (the matched ToolSpec's fields):
    steps = [event for event in events if isinstance(event, ToolActivity)]
    assert [step.tool_name for step in steps] == ["read", "read"]


async def test_a_single_subtask_batch_status_is_singular() -> None:
    # The count line is user-facing, so "1 subtask" is not "1 subtasks".
    store = InMemoryTaskStore()
    progress = RecordingProgressSink()
    await _tool(store, EchoInferenceBackend()).invoke(
        _call({"instructions": ["only one"]}, progress=progress)
    )
    assert list(progress.events) == [
        StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail="delegating 1 subtask")
    ]


async def test_one_shared_tool_routes_each_calls_progress_to_its_own_sink() -> None:
    # The built-once-shared SpawnSubagentsTool holds no per-stream state: the sink rides each
    # call's stamp, so two streams' progress never crosses. A sink bound at construction (the
    # naive per-stream fix) could not even express two sinks through one shared tool; here one
    # tool routes call A to sink A and call B to sink B, proving the per-call isolation.
    store = InMemoryTaskStore()
    tool = _tool(store, EchoInferenceBackend())  # tool-less subagents: only the batch status
    sink_a, sink_b = RecordingProgressSink(), RecordingProgressSink()
    await tool.invoke(_call({"instructions": ["a"]}, progress=sink_a))
    await tool.invoke(_call({"instructions": ["b", "c"]}, progress=sink_b))
    assert list(sink_a.events) == [
        StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail="delegating 1 subtask")
    ]
    assert list(sink_b.events) == [
        StatusUpdate(state=SUBAGENT_PROGRESS_STATE, detail="delegating 2 subtasks")
    ]


async def test_object_items_carry_model_and_context_onto_the_task() -> None:
    store = InMemoryTaskStore()
    tool = SpawnSubagentsTool(
        SubagentRunner(
            store,
            SubagentRoster(
                entries={
                    "subagent": _profile(EchoInferenceBackend(), "subagent"),
                    "fast": _profile(EchoInferenceBackend(), "fast"),
                },
                default="subagent",
            ),
            FixedClock(),
        ),
        store,
        FixedClock(),
        task_id_factory=_counter(),
    )
    result = await tool.invoke(
        _call(
            {
                "instructions": [
                    {"instruction": "translate", "model": "fast", "context": "the material"},
                    "plain one",
                ]
            }
        )
    )
    assert result.is_error is False
    first, second = await store.get_task("st-1"), await store.get_task("st-2")
    assert first is not None
    assert second is not None
    assert (first.instruction, first.model, first.context) == ("translate", "fast", "the material")
    assert (second.instruction, second.model, second.context) == ("plain one", "", "")


async def test_a_stringified_object_item_is_parsed_as_the_object_form() -> None:
    # Live gemma-4-12B JSON-encodes the object form into the string slot (ADR-0018 addendum);
    # the pick must not silently degrade to "run the JSON blob as an instruction".
    store = InMemoryTaskStore()
    tool = SpawnSubagentsTool(
        SubagentRunner(
            store,
            SubagentRoster(
                entries={
                    "subagent": _profile(EchoInferenceBackend(), "subagent"),
                    "fast": _profile(EchoInferenceBackend(), "fast"),
                },
                default="subagent",
            ),
            FixedClock(),
        ),
        store,
        FixedClock(),
        task_id_factory=_counter(),
    )
    result = await tool.invoke(
        _call({"instructions": ['{"instruction": "name a color", "model": "fast"}']})
    )
    assert result.is_error is False
    task = await store.get_task("st-1")
    assert task is not None
    assert (task.instruction, task.model) == ("name a color", "fast")


async def test_a_stringified_object_item_is_still_validated() -> None:
    # The diverted form goes through the same validation. An unknown pick is an error the
    # cortex can correct, not a silent fallback.
    store = InMemoryTaskStore()
    result = await _tool(store, EchoInferenceBackend()).invoke(
        _call({"instructions": ['{"instruction": "go", "model": "ghost"}']})
    )
    assert result.is_error is True
    assert "unknown subagent model 'ghost'" in result.content


@pytest.mark.parametrize(
    "text",
    [
        "{not json, just braces in an instruction",  # invalid JSON -> a plain instruction
        '{"model": "fast"}',  # a JSON object without 'instruction' -> a plain instruction
        '  {"instruction": "indented ok"}',  # leading whitespace still detected as JSON
    ],
)
async def test_brace_strings_that_are_not_object_items_stay_plain_instructions(
    text: str,
) -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, EchoInferenceBackend()).invoke(_call({"instructions": [text]}))
    assert result.is_error is False
    task = await store.get_task("st-1")
    assert task is not None
    # The third case IS a valid object item, so its instruction is the unwrapped text.
    expected = "indented ok" if "indented ok" in text else text
    assert task.instruction == expected
    assert task.model == ""


async def test_the_dispatchers_taint_stamp_rides_onto_every_task() -> None:
    # The dispatcher stamped the call because the turn had read untrusted content (ADR-0018);
    # the tool copies that onto each task so the runner's ADR-0017 resolution sees it.
    store = InMemoryTaskStore()
    await _tool(store, EchoInferenceBackend()).invoke(
        _call({"instructions": ["a", "b"]}, tainted=True)
    )
    first, second = await store.get_task("st-1"), await store.get_task("st-2")
    assert first is not None
    assert second is not None
    assert (first.tainted, second.tainted) == (True, True)


_BAD_ARGUMENTS: list[tuple[dict[str, object], str]] = [
    ({}, "non-empty 'instructions' array"),
    ({"instructions": []}, "non-empty 'instructions' array"),
    ({"instructions": [123]}, "each instruction must be a non-empty string"),
    ({"instructions": ["  "]}, "each instruction must be a non-empty string"),
    ({"instructions": [{}]}, "each instruction must be a non-empty string"),
    ({"instructions": [{"instruction": "  "}]}, "each instruction must be a non-empty string"),
    ({"instructions": [{"instruction": "go", "model": 3}]}, "'model' of a subtask"),
    (
        {"instructions": [{"instruction": "go", "model": "ghost"}]},
        "unknown subagent model 'ghost'; options: subagent",
    ),
    ({"instructions": [{"instruction": "go", "context": 3}]}, "'context' of a subtask"),
    ({"instructions": ["go"] * (MAX_SPAWN_BATCH + 1)}, f"at most {MAX_SPAWN_BATCH} subtasks"),
]


@pytest.mark.parametrize(("arguments", "message"), _BAD_ARGUMENTS)
async def test_bad_arguments_are_an_error_result(
    arguments: dict[str, object], message: str
) -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, EchoInferenceBackend()).invoke(_call(arguments))
    assert result.is_error is True
    assert message in result.content
    assert await store.get_task("st-1") is None  # nothing was spawned


async def test_a_batch_at_the_cap_still_runs_every_subtask() -> None:
    # The boundary the refusal above sits one past: an over-cap batch is refused, a batch of
    # exactly MAX_SPAWN_BATCH is ordinary work. Pins the comparison against an off-by-one that
    # would quietly cost the cortex its largest legitimate delegation.
    store = InMemoryTaskStore()
    batch = [f"task {n}" for n in range(MAX_SPAWN_BATCH)]
    result = await _tool(store, EchoInferenceBackend()).invoke(_call({"instructions": batch}))
    assert result.is_error is False
    assert result.content.count("[subagent ") == MAX_SPAWN_BATCH
    assert await store.get_task(f"st-{MAX_SPAWN_BATCH}") is not None


def _spec_of(runner: SubagentRunner) -> ToolSpec:
    return SpawnSubagentsTool(runner, InMemoryTaskStore(), FixedClock()).spec


def _model_property(spec: ToolSpec) -> dict[str, Any] | None:
    items = cast("dict[str, Any]", spec.parameters["properties"]["instructions"]["items"])
    item_object = cast("dict[str, Any]", items["anyOf"][1])
    return cast("dict[str, Any] | None", item_object["properties"].get("model"))


async def test_the_spec_advertises_the_roster_to_a_tool_less_wiring() -> None:
    store = InMemoryTaskStore()
    roster = SubagentRoster(
        entries={
            "subagent": _profile(EchoInferenceBackend(), "subagent", "the robust default"),
            "fast": _profile(EchoInferenceBackend(), "fast", "small and quick"),
        },
        default="subagent",
    )
    spec = _spec_of(SubagentRunner(store, roster, FixedClock()))
    model = _model_property(spec)
    assert model is not None
    assert model["enum"] == ["fast", "subagent"]  # sorted, deterministic
    assert "'fast' (small and quick)" in model["description"]
    assert "'subagent' (the robust default)" in model["description"]
    assert "default 'subagent'" in model["description"]
    assert "untrusted external content" in spec.description  # the ADR-0017 caveat is advertised
    # The measured trade-off is advertised, not a blanket parallel claim (ADR-0012 addendum):
    # distinct models overlap, same model serializes, so spreading is the wall-clock lever.
    assert "on distinct models run in parallel" in spec.description
    assert "share one model run one after another" in spec.description
    assert "spread independent subtasks across models" in spec.description
    assert "worth parallelizing" not in spec.description  # the old blanket overclaim is gone


async def test_the_spec_omits_the_model_knob_when_subagents_hold_tools() -> None:
    # ADR-0017 rule 2b pins every spawn in a tools-enabled wiring, so advertising a model
    # choice would be a knob that cannot do anything. The spec is honest about the wiring.
    store = InMemoryTaskStore()
    roster = SubagentRoster(
        entries={
            "subagent": _profile(EchoInferenceBackend(), "subagent"),
            "fast": _profile(EchoInferenceBackend(), "fast"),
        },
        default="subagent",
    )
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    spec = _spec_of(SubagentRunner(store, roster, FixedClock(), tools=dispatcher))
    assert _model_property(spec) is None
    assert "default subagent model" in spec.description
    # One model available means the subtasks share its backend and serialize; the note says so
    # rather than leaving the blanket parallel impression (ADR-0012 addendum).
    assert "run one after another" in spec.description
    assert "rather than running them in parallel" in spec.description


async def test_the_spec_omits_the_model_knob_for_a_single_entry_roster() -> None:
    # One entry = no choice to advertise, whatever the tool wiring.
    store = InMemoryTaskStore()
    spec = _spec_of(_runner(store, EchoInferenceBackend(), "subagent"))
    assert _model_property(spec) is None
    assert "default subagent model" in spec.description
    assert "run one after another" in spec.description  # single entry serializes too


async def test_the_spec_advertises_the_batch_cap() -> None:
    # The cap is told to the model twice over (a schema bound a grammar can enforce, and prose
    # for a model that reads only the description), so a refusal is a correction and not a
    # surprise. The runtime check stays the authority; this is what keeps it from firing.
    store = InMemoryTaskStore()
    spec = _spec_of(_runner(store, EchoInferenceBackend(), "subagent"))
    instructions = cast("dict[str, Any]", spec.parameters["properties"]["instructions"])
    assert instructions["maxItems"] == MAX_SPAWN_BATCH
    assert f"at most {MAX_SPAWN_BATCH}" in instructions["description"]
    assert f"At most {MAX_SPAWN_BATCH} subtasks per call" in spec.description
