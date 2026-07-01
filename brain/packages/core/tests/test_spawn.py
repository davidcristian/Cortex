"""Behavior tests for the spawn_subagents built-in tool (ADR-0010)."""

from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    EchoInferenceBackend,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    Message,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SpawnSubagentsTool,
    SubagentResources,
    SubagentRunner,
    TextChunk,
    ToolCall,
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


def _runner(store: InMemoryTaskStore, backend: InferenceBackend, model: str) -> SubagentRunner:
    resources = SubagentResources(
        backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
        scheduler=ResourceBudgetScheduler(8.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
    )
    return SubagentRunner(store, resources, FixedClock())


def _tool(store: InMemoryTaskStore, backend: InferenceBackend) -> SpawnSubagentsTool:
    return SpawnSubagentsTool(
        _runner(store, backend, "subagent"), store, FixedClock(), task_id_factory=_counter()
    )


def _call(arguments: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name="spawn_subagents", arguments=arguments)


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


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "non-empty 'instructions' array"),
        ({"instructions": []}, "non-empty 'instructions' array"),
        ({"instructions": [123]}, "must be a non-empty string"),
        ({"instructions": ["  "]}, "must be a non-empty string"),
    ],
)
async def test_bad_arguments_are_an_error_result(
    arguments: dict[str, object], message: str
) -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, EchoInferenceBackend()).invoke(_call(arguments))
    assert result.is_error is True
    assert message in result.content
    assert await store.get_task("st-1") is None  # nothing was spawned
