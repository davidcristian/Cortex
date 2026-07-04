"""Behavior tests for the spawn_subagents built-in tool (ADR-0010/0018)."""

from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from cortex_core import (
    EchoInferenceBackend,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    VramBudgetPlacer,
)

_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _AT


class FailingBackend:
    """Yields one delta then fails. Every subagent driven by it comes back ok=False."""

    async def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
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


def _call(arguments: dict[str, object], *, tainted: bool = False) -> ToolCall:
    return ToolCall(id="c1", name="spawn_subagents", arguments=arguments, tainted=tainted)


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
    assert result.content == "[subagent 1] FAILED: boom"


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


async def test_the_spec_omits_the_model_knob_for_a_single_entry_roster() -> None:
    # One entry = no choice to advertise, whatever the tool wiring.
    store = InMemoryTaskStore()
    spec = _spec_of(_runner(store, EchoInferenceBackend(), "subagent"))
    assert _model_property(spec) is None
    assert "default subagent model" in spec.description
