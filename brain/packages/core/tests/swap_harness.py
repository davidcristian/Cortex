"""Shared fakes and setup for the swap suites: one handoff run over fake adapters."""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from cortex_core import (
    DRAINING_DETAIL,
    LOADING_DETAIL,
    RESTORING_DETAIL,
    WORKING_DETAIL,
    AdmitAllScheduler,
    DecodeCadence,
    DispatchBudget,
    EscalationRefs,
    EscalationSlot,
    GenerationBounds,
    HandoffRecord,
    HandoffState,
    HandoffStoreError,
    HashEmbedder,
    InferenceError,
    InferenceEvent,
    InMemoryHandoffStore,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    Message,
    PlacementRequest,
    RecordingSleeper,
    ResidencyPlan,
    Role,
    ScriptedModelHost,
    StatusUpdate,
    SwapConductor,
    SwappingModelManager,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolSpec,
    TurnCapabilities,
    TurnEvent,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.memory import MemoryRecord

SESSION = "s-handoff"
TURN = "t-handoff"
NONCE = "f00ddeadbeef0001"
USER_TEXT = "work out what is wrong with this proof"
CORTEX_TEXT = "handing this to the deep model"
BRIEF = "check the induction step; the base case holds"
CORTEX_URL = "http://llama-cortex:8080"
BRAIN_URL = "http://llama-brain:8081"
_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)

# A handoff's status details are always a prefix of this list: one that stops early says less.
SWAP_WINDOW = [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]


class TickingClock:
    """A clock that advances one second each time it is read, and never waits."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


class Gate:
    """A pause point: a fake sets ``reached`` and blocks until the test sets ``release``."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def pause(self) -> None:
        self.reached.set()
        await self.release.wait()

    async def arrived(self) -> None:
        """Wait for the pause point, under a timeout so a miss fails the test instead of hanging."""
        async with asyncio.timeout(5.0):
            await self.reached.wait()


class WitnessingScheduler(AdmitAllScheduler):
    """The subagent pool, counting its drains and recording what was running at each undrain."""

    def __init__(self) -> None:
        super().__init__()
        self.drains = 0
        self.reopened: list[frozenset[str]] = []
        # Set later by build_harness: the pool is created before the host it watches.
        self.host: ScriptedModelHost | None = None

    async def drain(self, *, timeout_s: float) -> bool:
        self.drains += 1
        return await super().drain(timeout_s=timeout_s)

    def undrain(self) -> None:
        if self.host is not None:
            self.reopened.append(frozenset(self.host.running))
        super().undrain()


@dataclass(frozen=True, slots=True)
class StatusWitness:
    """What the system had done at the moment one swap-window status was sent."""

    detail: str
    drains: int
    host_ops: tuple[tuple[str, str], ...]
    record_states: tuple[HandoffState, ...]
    deep_calls: int


class RecordingHandoffStore(InMemoryHandoffStore):
    """Records every state written, so a test can check a record reached DONE before deletion."""

    def __init__(
        self,
        *,
        put_gate: Gate | None = None,
        fail: Exception | None = None,
        fail_settle: HandoffState | None = None,
    ) -> None:
        super().__init__()
        self.states: list[HandoffState] = []
        self.deleted: list[str] = []
        self._put_gate = put_gate
        self._fail = fail
        self._fail_settle = fail_settle

    async def put(self, record: HandoffRecord) -> None:
        if self._fail is not None:
            raise self._fail
        self.states.append(record.state)
        await super().put(record)
        if self._put_gate is not None:
            await self._put_gate.pause()

    async def transition(
        self, handoff_id: str, state: HandoffState, *, failure: str | None = None
    ) -> bool:
        """Like the in-memory store, except that ``fail_settle`` raises for that state once."""
        if state is self._fail_settle:
            self._fail_settle = None
            msg = f"redis refused the {state.value} write"
            raise HandoffStoreError(msg)
        return await super().transition(handoff_id, state, failure=failure)

    async def delete(self, handoff_id: str) -> None:
        self.deleted.append(handoff_id)
        await super().delete(handoff_id)


class RecordingSessionStore(InMemorySessionStore):
    """Session store that can pause after the deep model's reply is safely persisted."""

    def __init__(self, *, append_gate: Gate | None = None, gate_after: int = 3) -> None:
        super().__init__()
        self.appends = 0
        self._gate = append_gate
        self._gate_after = gate_after

    async def append(self, session_id: str, message: Message) -> None:
        await super().append(session_id, message)
        self.appends += 1
        if self._gate is not None and self.appends == self._gate_after:
            await self._gate.pause()


class ScriptedBrainBackend:
    """The deep model's scripted stream: some text, optionally paused or killed mid-flight."""

    def __init__(
        self,
        *,
        chunks: Sequence[str] = ("a deep ", "answer"),
        gate: Gate | None = None,
        gate_after: int = 1,
        fail_after: int | None = None,
        tool_calls: Sequence[ToolCall] = (),
        cadences: Sequence[DecodeCadence | None] = (),
    ) -> None:
        self.calls = 0
        self.closed = False
        self.seen: list[Message] = []
        self.models: list[str] = []
        self._chunks = list(chunks)
        self._gate = gate
        self._gate_after = gate_after
        self._fail_after = fail_after
        self._tool_calls = list(tool_calls)
        self._cadences = list(cadences)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del tools, schema, bounds
        self.calls += 1
        self.models.append(model)
        self.seen = list(messages)
        if self.calls <= len(self._tool_calls):
            yield self._tool_calls[self.calls - 1]
            cadence = self._cadence_for_round()
            if cadence is not None:
                yield cadence
            return
        try:
            for index, chunk in enumerate(self._chunks):
                if self._fail_after is not None and index == self._fail_after:
                    msg = "the deep model's server died mid-stream"
                    raise InferenceError(msg)
                if self._gate is not None and index == self._gate_after:
                    await self._gate.pause()
                yield TextChunk(chunk)
            cadence = self._cadence_for_round()
            if cadence is not None:
                yield cadence
        finally:
            self.closed = True

    def _cadence_for_round(self) -> DecodeCadence | None:
        """This round's scripted timings; the last entry is reused for every later round."""
        if not self._cadences:
            return None
        return self._cadences[min(self.calls - 1, len(self._cadences) - 1)]


def request() -> PlacementRequest:
    """One subagent placement request, used to check the pool admits again after a handoff."""
    return PlacementRequest("subagent", vram_gb=1.0, cpus=1.0, memory_gb=1.0)


# The only host call a handoff makes before it commits to anything: it asks whether there is a
# deep tier to load. Assertions that nothing was evicted compare against this exact list.
PREFLIGHT_CALLS = [("status", "brain")]


def plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "drain_timeout_s": 60.0,
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def prepared_slot(
    *,
    brief: str | None = BRIEF,
    taint: TaintLedger | None = None,
    tail: Sequence[Message] = (),
    budget: DispatchBudget | None = None,
) -> EscalationSlot:
    """A slot as the engine leaves it at the end of the tool loop: prepared, filled, tail kept."""
    ledger = taint if taint is not None else TaintLedger()
    working = [Message(role=Role.USER, text=USER_TEXT, at=_AT, turn_id=TURN)]
    base_len = len(working)
    working.extend(tail)
    return EscalationSlot(
        refs=EscalationRefs(
            working=working,
            taint=ledger,
            nonce=NONCE,
            budget=budget if budget is not None else DispatchBudget(),
            base_len=base_len,
        ),
        brief=brief,
    )


@dataclass(slots=True)
class Fakes:
    """The four outermost adapters a test may script; anything left out gets a default."""

    host: ScriptedModelHost | None = None
    handoffs: RecordingHandoffStore | None = None
    sessions: RecordingSessionStore | None = None
    backend: ScriptedBrainBackend | None = None


def recaller() -> MemoryRecaller:
    """A real MemoryRecaller over in-memory adapters, for checking the durable store survives."""
    minted = 0

    def next_id() -> str:
        nonlocal minted
        minted += 1
        return f"m{minted}"

    return MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), TickingClock(), id_factory=next_id)


@dataclass(slots=True)
class Harness:
    """One fully composed handoff, plus the fakes a test scripts and checks."""

    host: ScriptedModelHost
    manager: SwappingModelManager
    handoffs: RecordingHandoffStore
    sessions: RecordingSessionStore
    scheduler: WitnessingScheduler
    backend: ScriptedBrainBackend
    conductor: SwapConductor
    residency: ResidencyPlan
    memory: MemoryRecaller
    pooled: bool
    statuses: list[StatusWitness] = field(default_factory=list[StatusWitness])

    def observe(self, event: TurnEvent) -> TurnEvent:
        """Record what the system had done when a status was sent, and pass the event on."""
        if isinstance(event, StatusUpdate):
            self.statuses.append(
                StatusWitness(
                    detail=event.detail,
                    drains=self.scheduler.drains,
                    host_ops=tuple(self.host.calls),
                    record_states=tuple(self.handoffs.states),
                    deep_calls=self.backend.calls,
                )
            )
        return event

    async def seed_session(self) -> None:
        """Persist what the cortex phase already persisted before it escalated."""
        await self.sessions.append(
            SESSION, Message(role=Role.USER, text=USER_TEXT, at=_AT, turn_id=TURN)
        )
        await self.sessions.append(
            SESSION, Message(role=Role.ASSISTANT, text=CORTEX_TEXT, at=_AT, turn_id=TURN)
        )

    async def remembered(self) -> list[MemoryRecord]:
        """Every exchange this handoff wrote to durable memory, read back out of it."""
        hits = await self.memory.recall(USER_TEXT, k=5, session_id=SESSION, turn_id="t")
        return [hit.record for hit in hits]


def build_harness(
    fakes: Fakes | None = None,
    *,
    residency: ResidencyPlan | None = None,
    capabilities: TurnCapabilities | None = None,
    scheduler: WitnessingScheduler | None = None,
    with_scheduler: bool = True,
) -> Harness:
    """Compose the real conductor over fakes, exactly as the composition root composes it."""
    scripted = fakes if fakes is not None else Fakes()
    used_plan = residency if residency is not None else plan()
    used_host = (
        scripted.host
        if scripted.host is not None
        else ScriptedModelHost(running=[used_plan.cortex_model])
    )
    used_handoffs = scripted.handoffs if scripted.handoffs is not None else RecordingHandoffStore()
    used_sessions = scripted.sessions if scripted.sessions is not None else RecordingSessionStore()
    used_backend = scripted.backend if scripted.backend is not None else ScriptedBrainBackend()
    clock = TickingClock()
    manager = SwappingModelManager(
        used_host,
        {used_plan.cortex_model: CORTEX_URL, used_plan.brain_model: BRAIN_URL},
        used_plan,
        clock,
        RecordingSleeper(),
    )
    pool = scheduler if scheduler is not None else WitnessingScheduler()
    pool.host = used_host
    memory = recaller()
    caps = replace(capabilities if capabilities is not None else TurnCapabilities(), memory=memory)
    return Harness(
        host=used_host,
        manager=manager,
        handoffs=used_handoffs,
        sessions=used_sessions,
        scheduler=pool,
        backend=used_backend,
        residency=used_plan,
        memory=memory,
        pooled=with_scheduler,
        conductor=SwapConductor(
            used_handoffs,
            manager,
            BrainPhase(used_sessions, used_backend, clock, used_plan.brain_model, caps),
            used_plan,
            clock,
            pool if with_scheduler else None,
        ),
    )


async def run_handoff(
    harness: Harness, slot: EscalationSlot, *, turn_id: str = TURN
) -> list[TurnEvent]:
    """Run one handoff to the end, collecting every event it put on the turn's stream."""
    events: list[TurnEvent] = []
    stream = harness.conductor.run_handoff(slot, session_id=SESSION, turn_id=turn_id)
    try:
        async for event in stream:
            events.append(harness.observe(event))  # noqa: PERF401 - one event at a time
    finally:
        await stream.aclose()
    return events


def assert_the_window_announced_real_progress(live: Harness) -> None:
    """Check every swap-window status against the work it reports."""
    seen = [witness.detail for witness in live.statuses]
    assert seen == SWAP_WINDOW[: len(seen)]
    for witness in live.statuses:
        _WINDOW_CHECKS[witness.detail](live, witness)


def _draining_was_true(live: Harness, seen: StatusWitness) -> None:
    """The draining status is sent before the drain, with the record already saved."""
    assert seen.drains == 0
    assert seen.host_ops == (("status", live.residency.brain_model),)
    assert seen.record_states[-1] is HandoffState.READY
    assert seen.deep_calls == 0


def _loading_was_true(live: Harness, seen: StatusWitness) -> None:
    """The loading status is sent once the pool is drained and before the model is loaded."""
    assert seen.drains == (1 if live.pooled else 0)
    assert ("start", live.residency.brain_model) not in seen.host_ops
    assert ("stop", live.residency.cortex_model) not in seen.host_ops
    assert seen.record_states[-1] is HandoffState.READY


def _working_was_true(live: Harness, seen: StatusWitness) -> None:
    """The working status is the only one that reports the deep model is already loaded."""
    assert ("start", live.residency.brain_model) in seen.host_ops
    assert ("status", live.residency.brain_model) in seen.host_ops
    assert seen.record_states[-1] is HandoffState.BRAIN_ACTIVE
    assert seen.deep_calls == 0


def _restoring_was_true(live: Harness, seen: StatusWitness) -> None:
    """The restoring status is sent after the deep model ran and before it is stopped."""
    assert seen.deep_calls >= 1
    assert ("stop", live.residency.brain_model) not in seen.host_ops
    assert ("start", live.residency.cortex_model) not in seen.host_ops
    assert seen.record_states[-1] is HandoffState.BRAIN_ACTIVE


_WINDOW_CHECKS: dict[str, Callable[[Harness, StatusWitness], None]] = {
    DRAINING_DETAIL: _draining_was_true,
    LOADING_DETAIL: _loading_was_true,
    WORKING_DETAIL: _working_was_true,
    RESTORING_DETAIL: _restoring_was_true,
}
