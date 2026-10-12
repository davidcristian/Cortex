import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from cortex_core import (
    DecodeStop,
    GenerationBounds,
    InferenceBackend,
    InferenceEvent,
    InMemoryTaskStore,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    SpawnSubagentsTool,
    StopReason,
    SubagentProfile,
    SubagentResources,
    SubagentResult,
    SubagentRoster,
    SubagentRunner,
    SubagentTask,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
    VramBudgetPlacer,
)

_AT = datetime(2026, 10, 12, 4, 30, tzinfo=UTC)
_SUITE_BOUND_S = 10.0
_LOOKUP = ToolSpec(name="lookup", description="look something up", parameters={})
_ROUNDS_SPENT = (
    "the subtask was still calling tools after all 8 rounds of tool calls a run is given, so it "
    "never wrote an answer; treat the subtask as unanswered, and split or narrow it before "
    "delegating it again"
)
_WRITTEN = "".join(f"looking {n}. " for n in range(1, 9))


class FixedClock:
    def now(self) -> datetime:
        return _AT


class CallsEveryRoundBackend:
    """Writes a line and calls a tool on every round, answering only on round ``answer_on``."""

    def __init__(self, *, answer_on: int | None = None, cap_first: bool = False) -> None:
        self._answer_on = answer_on
        self._cap_first = cap_first
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
        if self.calls == self._answer_on:
            yield TextChunk("the answer.")
            return
        yield TextChunk(f"looking {self.calls}. ")
        yield ToolCall(id=f"c{self.calls}", name="lookup", arguments={"n": self.calls})
        if self._cap_first and self.calls == 1:
            yield DecodeStop(StopReason.CAPPED)


class AnsweringToolRegistry:
    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (_LOOKUP,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        return ToolResult(call_id=call.id, content="42", trust=Trust.TRUSTED)


def _runner(
    store: InMemoryTaskStore, gpu: InferenceBackend, cpu: InferenceBackend | None = None
) -> SubagentRunner:
    resources = SubagentResources(
        backends={PlacementTarget.GPU: gpu, PlacementTarget.CPU: gpu if cpu is None else cpu},
        scheduler=ResourceBudgetScheduler(4.0, 8.0),
        placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        request=PlacementRequest("subagent", vram_gb=3.0, cpus=2.0, memory_gb=2.0),
    )
    roster = SubagentRoster(
        entries={"subagent": SubagentProfile(resources=resources)}, default="subagent"
    )
    tools = ToolDispatcher(AnsweringToolRegistry(), RecordingAuditSink(), FixedClock())
    return SubagentRunner(store, roster, FixedClock(), tools=tools)


async def _run(runner: SubagentRunner, store: InMemoryTaskStore) -> SubagentResult:
    await store.put_task(SubagentTask(id="t1", instruction="find it", context="", at=_AT))
    async with asyncio.timeout(_SUITE_BOUND_S):
        return await runner.run("t1")


async def test_a_subagent_that_spends_every_round_is_reported_unanswered() -> None:
    store = InMemoryTaskStore()
    backend = CallsEveryRoundBackend()
    result = await _run(_runner(store, backend), store)
    assert (result.ok, result.detail, result.output) == (False, _ROUNDS_SPENT, _WRITTEN)
    assert await store.get_result("t1") == result
    assert backend.calls == 8


async def test_a_gpu_attempt_that_spent_its_rounds_is_not_re_run_on_the_cpu() -> None:
    store = InMemoryTaskStore()
    gpu, cpu = CallsEveryRoundBackend(), CallsEveryRoundBackend()
    await _run(_runner(store, gpu, cpu), store)
    assert (gpu.calls, cpu.calls) == (8, 0)


async def test_the_cortex_reads_the_round_limit_and_not_what_the_subagent_wrote() -> None:
    store = InMemoryTaskStore()
    spawn = SpawnSubagentsTool(_runner(store, CallsEveryRoundBackend()), store, FixedClock())
    call = ToolCall(
        id="s1",
        name="spawn_subagents",
        arguments={"instructions": ["find it"]},
        stamp=TurnStamp(tainted=False, budget=None, progress=None),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await spawn.invoke(call)
    assert result.content == f"[subagent 1] FAILED: {_ROUNDS_SPENT}"


async def test_a_subagent_that_answers_in_its_last_round_has_answered() -> None:
    store = InMemoryTaskStore()
    result = await _run(_runner(store, CallsEveryRoundBackend(answer_on=8)), store)
    assert (result.ok, result.detail) == (True, "")
    assert result.output == "".join(f"looking {n}. " for n in range(1, 8)) + "the answer."


async def test_a_cap_in_any_round_is_reported_ahead_of_the_round_limit() -> None:
    store = InMemoryTaskStore()
    result = await _run(_runner(store, CallsEveryRoundBackend(cap_first=True)), store)
    assert result.ok is False
    assert result.detail.startswith("the subtask stopped at a token limit")
