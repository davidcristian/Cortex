"""Behavior tests for the total generation cap on a delegated run (ADR-0005 total-cap addendum)."""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    AttemptBounds,
    GenerationBounds,
    InferenceBackend,
    InferenceError,
    InMemoryTaskStore,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SpawnSubagentsTool,
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
# Every wait in this file sits under this, so a regression that reintroduces the unbounded run
# fails the check instead of hanging the suite.
_SUITE_BOUND_S = 10.0
# Small enough that a runaway is stopped in milliseconds, large enough that a scripted stream of a
# handful of chunks always finishes inside it on any machine this suite runs on.
_DEADLINE_S = 0.25
_REQUEST = PlacementRequest("subagent", vram_gb=3.0, cpus=2.0, memory_gb=2.0)


class FixedClock:
    """A clock pinned to one instant. The attempt only needs it to stamp tool messages."""

    def now(self) -> datetime:
        return _AT


class RunawayBackend:
    """The failure a stall detector cannot see: never silent, never finished."""

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
            # The lease discipline `LlamaCppBackend` really has: whatever it holds for the stream
            # is released here, so this flag is "the lease is back" said in a fake's terms.
            self.closed = True


class LeasedRunawayBackend:
    """A runaway that holds a real model lease for its stream, as ``LlamaCppBackend`` does."""

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
    """Replays one event list per call and records the ``bounds`` each request carried."""

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
    """Fails the way a wedged server does once its stall ceiling has fired, and no faster."""

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
    """Raises a bare ``TimeoutError`` from below: a socket that timed out, not our deadline.

    ``TimeoutError`` is an ``OSError`` in Python, so a real transport can raise one that never
    passed through an adapter's translation, and `asyncio.timeout` raises the very same class.
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
        del model, messages, tools, schema, bounds
        yield TextChunk("partial ")
        raise TimeoutError


_LOOKUP = ToolSpec(name="lookup", description="look something up", parameters={})


class HangingToolRegistry:
    """A tool that is dispatched and never answers: a sidecar that took the call and stopped."""

    def __init__(self) -> None:
        self.dispatched = asyncio.Event()

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (_LOOKUP,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.dispatched.set()
        await asyncio.Event().wait()  # never set: the dispatch outlives the attempt
        return ToolResult(call_id=call.id, content="", trust=Trust.TRUSTED)


class AnsweringToolRegistry:
    """The same tool, answering at once, so a loop reaches its second completion."""

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
    """One roster entry over ``backend``, with ``cpu`` as the overflow target when given."""
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


# --- the deadline ----------------------------------------------------------------------------


async def test_a_subagent_that_never_stops_talking_is_stopped_at_its_deadline() -> None:
    """The defect itself: without the bound this call never returns and the suite hangs."""
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
    assert backend.chunks > 0  # it really did run away rather than failing to start
    assert await store.get_result("t1") == result  # the cortex reads it back from the store


async def test_the_cortex_can_tell_a_stopped_run_from_a_short_answer() -> None:
    """A cap that reported a fragment as an answer would have traded a hang for a lie."""
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
    assert "lorem lorem" not in aggregate.content  # the fragment is not read back as an answer
    stored = await store.get_result("t1")
    assert stored is not None
    assert stored.output.startswith("lorem ")  # but it is kept where an operator can read it


async def test_a_stopped_run_releases_its_admission_and_its_placement() -> None:
    """Both live-resource ledgers are back the instant the deadline reports, not eventually."""
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
            pass  # admitted at the whole budget: the stopped run charges nothing any more
    assert placer.place(PlacementRequest("peer", 3.0, 1.0, 1.0)).target is PlacementTarget.GPU


async def test_a_stopped_run_has_already_released_the_model_lease_when_it_returns() -> None:
    """Not "the lease comes back eventually" but "it was back before ``run`` returned"."""
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
    """The same property through the object that actually serializes the GPU: the lease lock."""
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
    """It bounds the attempt, not the stream: a sidecar that took a call and stopped is inside it.

    A subagent suspended in a dispatch holds exactly what one suspended in a generation holds, so
    a deadline that only covered decoding would leave the pool's worst case where it was.
    """
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
    assert registry.dispatched.is_set()  # the wait it was cut out of was a real dispatch


async def test_a_deadline_that_lands_mid_envelope_is_reported_as_the_deadline() -> None:
    """A cut envelope is malformed by construction, and saying so would name the wrong cause."""
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
    """The re-place exists for a backend that did not answer, and a runaway answered.

    Sending it to the slower tier would spend a second whole deadline to be told the same thing,
    and on the tier where a token budget is worth minutes rather than seconds.
    """
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
    assert cpu.calls == []  # never re-placed


async def test_a_wedged_stream_is_still_the_retryable_failure_under_a_generous_deadline() -> None:
    """The stated precedence, in the case where the two bounds cannot race."""
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
    assert "within its ceiling" in result.detail  # the wedge, named, and re-run rather than cut


async def test_a_timeout_from_below_the_deadline_is_the_backend_failing_not_a_truncation() -> None:
    """`TimeoutError` is an `OSError`, so it can arrive from a socket rather than from our bound."""
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
        bounds=AttemptBounds(),  # unbounded, which is where the misreport would have crashed
    )
    async with asyncio.timeout(_SUITE_BOUND_S):
        result = await runner.run("t1")
    assert result.ok is True
    assert result.output == "the re-run answered"
    assert "timed out below the delegated run's own deadline" in result.detail


# --- the token cap ---------------------------------------------------------------------------


async def test_the_token_cap_rides_every_completion_of_a_delegated_loop() -> None:
    """Per completion, because that is the unit ``n_predict`` bounds; rounds bound the rest."""
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
    """Both knobs unset is the byte-for-byte prior behaviour, which is what makes them opt-in."""
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


# --- the value ------------------------------------------------------------------------------


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
    """A zero deadline is not "never queue" the way a zero admission wait is; it is "never run"."""
    with pytest.raises(ValueError, match=message):
        AttemptBounds(**kwargs)  # pyright: ignore[reportArgumentType]
