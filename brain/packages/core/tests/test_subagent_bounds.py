import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    AttemptBounds,
    DecodeStop,
    GenerationBounds,
    InferenceBackend,
    InferenceError,
    InMemoryTaskStore,
    JsonSchema,
    MalformedToolCallError,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    StopReason,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SubagentTask,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    VramBudgetPlacer,
)
from cortex_core.inference import InferenceEvent

_AT = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
# Every wait here runs under _SUITE_BOUND_S, so a change that brought back the unbounded run
# fails instead of hanging the suite. _DEADLINE_S is small enough to stop a runaway in
# milliseconds and large enough for a few scripted chunks to finish on any machine.
_SUITE_BOUND_S = 10.0
_DEADLINE_S = 0.25
_REQUEST = PlacementRequest("subagent", vram_gb=3.0, cpus=2.0, memory_gb=2.0)


class FixedClock:
    """A clock fixed at one instant."""

    def now(self) -> datetime:
        return _AT


class RunawayBackend:
    """A backend that streams forever, so it is never silent and never finishes."""

    def __init__(self, *, chunk: str = "and also, ") -> None:
        self._chunk = chunk
        self.chunks = 0
        self.closed = False
        self.calls: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del messages, tools, schema, bounds
        self.calls.append(model)
        try:
            while True:
                self.chunks += 1
                await asyncio.sleep(0)
                yield TextChunk(self._chunk)
        finally:
            self.closed = True


class LeasedRunawayBackend:
    """A backend that streams forever while holding a model lease, as ``LlamaCppBackend`` does."""

    def __init__(self, manager: SingleResidentModelManager) -> None:
        self._manager = manager

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del messages, tools, schema, bounds
        async with self._manager.acquire(model):
            while True:
                await asyncio.sleep(0)
                yield TextChunk("on and on ")


class RecordingBackend:
    """Replays one event list per call and records the ``bounds`` of each request."""

    def __init__(self, steps: Sequence[Sequence[InferenceEvent]]) -> None:
        self._steps = list(steps)
        self._call = 0
        self.bounds_seen: list[GenerationBounds | None] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
        self.bounds_seen.append(bounds)
        step = self._steps[min(self._call, len(self._steps) - 1)]
        self._call += 1
        for event in step:
            yield event


class FailingBackend:
    """Fails only after the stall deadline has passed, as a stuck server does."""

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
        msg = "llama-server sent nothing for model 'subagent' within its ceiling"
        raise InferenceError(msg)


class InnerTimeoutBackend:
    """Raises a bare ``TimeoutError`` from below, as a timed-out socket does."""

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
        raise TimeoutError


_LOOKUP = ToolSpec(name="lookup", description="look something up", parameters={})


class HangingToolRegistry:
    """A tool that is dispatched and never answers, as a stopped sidecar would."""

    def __init__(self) -> None:
        self.dispatched = asyncio.Event()

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (_LOOKUP,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.dispatched.set()
        await asyncio.Event().wait()
        return ToolResult(call_id=call.id, content="", trust=Trust.TRUSTED)


class AnsweringToolRegistry:
    """The same tool, answering at once, so the loop reaches its second completion."""

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (_LOOKUP,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        return ToolResult(call_id=call.id, content="42", trust=Trust.TRUSTED)


def _resources(
    backend: InferenceBackend,
    *,
    scheduler: ResourceBudgetScheduler,
    placer: VramBudgetPlacer,
    cpu: InferenceBackend | None = None,
) -> SubagentResources:
    """One roster entry over ``backend``, with ``cpu`` as the overflow target if given."""
    return SubagentResources(
        backends={
            PlacementTarget.GPU: backend,
            PlacementTarget.CPU: (backend if cpu is None else cpu),
        },
        scheduler=scheduler,
        placer=placer,
        request=_REQUEST,
    )


def _runner(
    store: InMemoryTaskStore,
    resources: SubagentResources,
    *,
    bounds: AttemptBounds,
    tools: ToolDispatcher | None = None,
    constrain_output: bool = False,
) -> SubagentRunner:
    roster = SubagentRoster(
        entries={"subagent": SubagentProfile(resources=resources)}, default="subagent"
    )
    return SubagentRunner(
        store,
        roster,
        FixedClock(),
        tools=tools,
        constrain_output=constrain_output,
        bounds=bounds,
    )


async def _stored_task(store: InMemoryTaskStore, task_id: str = "t1") -> None:
    await store.put_task(SubagentTask(id=task_id, instruction="summarize", context="", at=_AT))


async def test_a_subagent_that_never_stops_talking_is_stopped_at_its_deadline() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RunawayBackend()
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    runner = _runner(
        store,
        _resources(backend, scheduler=scheduler, placer=placer),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "still generating after 0.25s" in result.detail
    assert "narrow it before delegating it again" in result.detail
    assert backend.chunks > 0
    assert await store.get_result("t1") == result


async def test_the_cortex_can_tell_a_stopped_run_from_a_short_answer() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    runner = _runner(
        store,
        _resources(RunawayBackend(chunk="lorem "), scheduler=scheduler, placer=placer),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    tool = SpawnSubagentsTool(runner, store, FixedClock(), task_id_factory=lambda: "t1")
    async with asyncio.timeout(_SUITE_BOUND_S):
        aggregate = await tool.invoke(
            ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": ["go"]})
        )
    assert "FAILED:" in aggregate.content
    assert "still generating after" in aggregate.content
    assert "lorem lorem" not in aggregate.content
    stored = await store.get_result("t1")
    assert stored is not None
    assert stored.output.startswith("lorem ")


async def test_a_stopped_run_releases_its_admission_and_its_placement() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    runner = _runner(
        store,
        _resources(RunawayBackend(), scheduler=scheduler, placer=placer),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        assert (await runner.run("t1")).ok is False
        async with scheduler.admit(PlacementRequest("peer", 1.0, 4.0, 8.0)):
            pass
    assert placer.place(PlacementRequest("peer", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


async def test_a_stopped_run_has_already_released_the_model_lease_when_it_returns() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RunawayBackend()
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert backend.closed is True


async def test_the_real_lease_a_stopped_run_held_can_be_taken_again() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    manager = SingleResidentModelManager("subagent", "http://llama-subagent:8082")
    runner = _runner(
        store,
        _resources(
            LeasedRunawayBackend(manager),
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        assert (await runner.run("t1")).ok is False
        async with manager.acquire("subagent") as lease:
            assert lease.endpoint == "http://llama-subagent:8082"


async def test_the_deadline_covers_a_tool_dispatch_the_subagent_is_waiting_on() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    registry = HangingToolRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), FixedClock())
    backend = RecordingBackend([[ToolCall(id="c1", name="lookup", arguments={})]])
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
        tools=dispatcher,
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "still generating after" in result.detail
    assert registry.dispatched.is_set()


async def test_a_deadline_that_lands_mid_envelope_is_reported_as_the_deadline() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    runner = _runner(
        store,
        _resources(
            RunawayBackend(chunk='{"reply": "'),
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
        constrain_output=True,
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "still generating after" in result.detail
    assert "malformed" not in result.detail


async def test_a_stopped_gpu_attempt_is_not_re_run_on_the_cpu() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    gpu, cpu = RunawayBackend(), RunawayBackend()
    runner = _runner(
        store,
        _resources(
            gpu,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            cpu=cpu,
        ),
        bounds=AttemptBounds(timeout_s=_DEADLINE_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert gpu.calls == ["subagent"]
    assert cpu.calls == []


async def test_a_wedged_stream_is_still_the_retryable_failure_under_a_generous_deadline() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    gpu, cpu = FailingBackend(), RecordingBackend([[TextChunk("the re-run answered")]])
    runner = _runner(
        store,
        _resources(
            gpu,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            cpu=cpu,
        ),
        bounds=AttemptBounds(timeout_s=_SUITE_BOUND_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert result.output == "the re-run answered"
    assert "within its ceiling" in result.detail


async def test_a_timeout_from_below_the_deadline_is_the_backend_failing_not_a_truncation() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    gpu, cpu = InnerTimeoutBackend(), RecordingBackend([[TextChunk("the re-run answered")]])
    runner = _runner(
        store,
        _resources(
            gpu,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            cpu=cpu,
        ),
        bounds=AttemptBounds(),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert result.output == "the re-run answered"
    assert "timed out below the delegated run's own deadline" in result.detail


async def test_the_token_cap_rides_every_completion_of_a_delegated_loop() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend(
        [[ToolCall(id="c1", name="lookup", arguments={})], [TextChunk("done")]]
    )
    dispatcher = ToolDispatcher(AnsweringToolRegistry(), RecordingAuditSink(), FixedClock())
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=256, timeout_s=_SUITE_BOUND_S),
        tools=dispatcher,
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert backend.bounds_seen == [GenerationBounds(max_tokens=256)] * 2


async def test_an_unbounded_attempt_sends_the_request_this_repo_has_always_sent() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend([[TextChunk("a short answer")]])
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.output == "a short answer"
    assert backend.bounds_seen == [None]


async def test_a_capped_completion_is_reported_as_cut_rather_than_answered() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend(
        [[TextChunk("the sea is a large body of wat"), DecodeStop(StopReason.CAPPED)]]
    )
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=1024, timeout_s=_SUITE_BOUND_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "stopped at a token limit" in result.detail
    assert "1024 decoded tokens per completion" in result.detail
    stored = await store.get_result("t1")
    assert stored is not None
    assert stored.output == "the sea is a large body of wat"


async def test_a_completion_that_finished_is_still_an_answer() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend([[TextChunk("blue."), DecodeStop(StopReason.FINISHED)]])
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=1024, timeout_s=_SUITE_BOUND_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert result.output == "blue."


async def test_a_backend_that_reports_no_reason_at_all_still_answers() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend([[TextChunk("a quiet answer.")]])
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=1024, timeout_s=_SUITE_BOUND_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert result.output == "a quiet answer."


async def test_an_unbounded_run_that_a_server_capped_quotes_no_bound_of_its_own() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend([[TextChunk("cut by the context"), DecodeStop(StopReason.CAPPED)]])
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "stopped at a token limit" in result.detail
    assert "this run's own cap" not in result.detail


async def test_a_cap_that_lands_mid_envelope_is_reported_as_the_cap() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend(
        [[TextChunk('{"reply": "half a sen'), DecodeStop(StopReason.CAPPED)]]
    )
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=64, timeout_s=_SUITE_BOUND_S),
        constrain_output=True,
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "stopped at a token limit" in result.detail
    assert "malformed" not in result.detail


async def test_a_capped_gpu_attempt_is_not_re_run_on_the_cpu() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    capped = [[TextChunk("cut"), DecodeStop(StopReason.CAPPED)]]
    gpu, cpu = RecordingBackend(capped), RecordingBackend(capped)
    runner = _runner(
        store,
        _resources(
            gpu,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            cpu=cpu,
        ),
        bounds=AttemptBounds(max_tokens=64, timeout_s=_SUITE_BOUND_S),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert gpu.bounds_seen == [GenerationBounds(max_tokens=64)]
    assert cpu.bounds_seen == []


async def test_one_capped_round_of_a_tool_loop_cuts_the_whole_attempt() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = RecordingBackend(
        [
            [ToolCall(id="c1", name="lookup", arguments={}), DecodeStop(StopReason.CAPPED)],
            [TextChunk("done."), DecodeStop(StopReason.FINISHED)],
        ]
    )
    dispatcher = ToolDispatcher(AnsweringToolRegistry(), RecordingAuditSink(), FixedClock())
    runner = _runner(
        store,
        _resources(
            backend,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
        ),
        bounds=AttemptBounds(max_tokens=64, timeout_s=_SUITE_BOUND_S),
        tools=dispatcher,
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is False
    assert "stopped at a token limit" in result.detail


# The adapter builds the model's tool calls only once the stream is over, so a cap that falls
# mid arguments leaves a JSON fragment and raises. Measured against a real server: a cap of 20 to
# 160 tokens on a long-argument call left 71 to 899 characters of fragment.
class CutToolCallBackend:
    """Reports the stop the way the real adapter does, then fails to build the model's call."""

    def __init__(self, *, stop: DecodeStop | None, error: InferenceError) -> None:
        self._stop = stop
        self._error = error
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
        yield TextChunk("about to call")
        if self._stop is not None:
            yield self._stop
        raise self._error


def _cut_runner(
    store: InMemoryTaskStore,
    gpu: InferenceBackend,
    cpu: InferenceBackend | None = None,
) -> SubagentRunner:
    return _runner(
        store,
        _resources(
            gpu,
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            cpu=cpu,
        ),
        bounds=AttemptBounds(max_tokens=1024, timeout_s=_SUITE_BOUND_S),
        tools=ToolDispatcher(AnsweringToolRegistry(), RecordingAuditSink(), FixedClock()),
    )


async def test_a_cap_inside_a_tool_call_is_reported_as_the_cap_not_a_dead_backend() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    backend = CutToolCallBackend(
        stop=DecodeStop(StopReason.CAPPED),
        error=MalformedToolCallError('malformed tool-call arguments: \'{"body":"In the real\''),
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await _cut_runner(store, backend).run("t1")
    assert result.ok is False
    assert "stopped at a token limit" in result.detail
    assert "1024 decoded tokens per completion" in result.detail
    assert "malformed tool-call arguments" not in result.detail
    stored = await store.get_result("t1")
    assert stored is not None
    assert stored.output == "about to call"


async def test_a_cut_tool_call_is_not_re_run_on_the_cpu() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    error = MalformedToolCallError('malformed tool-call arguments: \'{"path":"no\'')
    gpu = CutToolCallBackend(stop=DecodeStop(StopReason.CAPPED), error=error)
    cpu = CutToolCallBackend(stop=DecodeStop(StopReason.CAPPED), error=error)
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await _cut_runner(store, gpu, cpu).run("t1")
    assert result.ok is False
    assert (gpu.calls, cpu.calls) == (1, 0)


async def test_an_unparsable_tool_call_with_no_cap_reported_is_still_the_backends_fault() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    error = MalformedToolCallError("malformed tool-call arguments: '{oops'")
    gpu = CutToolCallBackend(stop=None, error=error)
    cpu = CutToolCallBackend(stop=None, error=error)
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await _cut_runner(store, gpu, cpu).run("t1")
    assert result.ok is False
    assert "malformed tool-call arguments" in result.detail
    assert "stopped at a token limit" not in result.detail
    assert (gpu.calls, cpu.calls) == (1, 1)


async def test_a_dead_backend_after_a_capped_round_is_still_a_dead_backend() -> None:
    store = InMemoryTaskStore()
    await _stored_task(store)
    gpu = CutToolCallBackend(
        stop=DecodeStop(StopReason.CAPPED),
        error=InferenceError("llama-server sent nothing for model 'subagent' within its ceiling"),
    )
    cpu = RecordingBackend([[TextChunk("the cpu answered."), DecodeStop(StopReason.FINISHED)]])
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await _cut_runner(store, gpu, cpu).run("t1")
    assert result.ok is True
    assert result.output == "the cpu answered."
    assert "sent nothing" in result.detail


def test_unbounded_is_what_a_deployment_that_asked_for_nothing_gets() -> None:
    assert AttemptBounds() == AttemptBounds(max_tokens=None, timeout_s=None)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_tokens": 0}, "max_tokens must be at least 1"),
        ({"max_tokens": -1}, "max_tokens must be at least 1"),
        ({"timeout_s": 0.0}, "timeout_s must be > 0"),
        ({"timeout_s": -1.0}, "timeout_s must be > 0"),
    ],
)
def test_a_bound_that_could_never_admit_an_answer_is_refused(
    kwargs: Mapping[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        AttemptBounds(**kwargs)  # pyright: ignore[reportArgumentType]
