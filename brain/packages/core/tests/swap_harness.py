"""Shared scaffolding for the swap suites: one handoff over fakes, and the invariants it owes.

Imported by ``test_swap_conductor.py`` (the sequence, step by step) and ``test_swap_chaos.py``
(the same sequence killed at every boundary), so both drive exactly the same composition: the
real ``SwapConductor`` over the real ``SwappingModelManager``, the real ``BrainPhase``, and the
real drain, with only the outermost adapters faked (the model host, the stores, the inference
backend). The point of the suites is that the orchestration is real; faking the conductor
itself would prove nothing.

``Gate`` is the one pausing primitive: a fake sets ``reached`` when the code gets to a named
boundary and blocks on ``release`` until the test lets go, so a test cancels the handoff exactly
there. Nothing here sleeps wall-clock.

Two witnesses live here because both suites need them and neither can reconstruct them
afterwards, a finished handoff having erased the state that would prove the ordering:

- ``StatusWitness``, one snapshot per swap-window status, taken by the collector the instant the
  event crosses the stream. It is what lets a status be checked against **the work it announces**
  rather than against the other statuses: an order among four strings is satisfied by four
  strings emitted at any four moments. Resuming a generator hands control straight to its
  consumer with no loop tick in between, so the snapshot is the machine state at the yield.
- ``WitnessingScheduler.reopened``, what the host was running each time admission reopened. The
  drain window must stay shut until the standing residency is back, and afterwards nothing can
  tell a window that reopened too early from one that reopened on time.
"""

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
    DispatchBudget,
    EscalationRefs,
    EscalationSlot,
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

# The swap window's four steps, in the only order they can honestly happen. Every handoff's
# status details are a PREFIX of this: one that stopped early says less, never something else.
SWAP_WINDOW = [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]


class TickingClock:
    """Advances one second per reading: monotone, deterministic, and free."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


class Gate:
    """One armed boundary: a fake fires ``reached`` there and blocks until ``release``."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def pause(self) -> None:
        self.reached.set()
        await self.release.wait()

    async def arrived(self) -> None:
        """Wait for the boundary to be reached; a bound, so a miss fails instead of hanging."""
        async with asyncio.timeout(5.0):
            await self.reached.wait()


class WitnessingScheduler(AdmitAllScheduler):
    """The pool, plus the two things about the drain window nothing else can observe after.

    ``drains`` counts the quiescings the conductor actually asked for, which is what pins a
    status announcing the drain to a moment before the drain rather than after it. ``reopened``
    records what the model host was running each time ``undrain`` reopened admission, which is
    the ordering the standing residency depends on: the pool starts taking delegated work the
    instant the window lifts, so a window lifted while an evicted tier is still stopped hands
    that work to a server nothing has restarted. Both are gone by the time a handoff ends.
    """

    def __init__(self) -> None:
        super().__init__()
        self.drains = 0
        self.reopened: list[frozenset[str]] = []
        # Set by ``build_harness``; the pool is composed before the host it watches exists.
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
    """What the machine had actually done at the instant one swap-window status was emitted."""

    detail: str
    drains: int
    host_ops: tuple[tuple[str, str], ...]
    record_states: tuple[HandoffState, ...]
    deep_calls: int


class RecordingHandoffStore(InMemoryHandoffStore):
    """Records every state written, so a record that reached DONE and was deleted is provable.

    The store keeps only the latest record and a clean handoff deletes it at the end, so "the
    record reached a terminal state" is not observable from the final state alone. Every write
    lands in ``put`` (the in-memory transition rewrites through it), so recording there counts
    each state exactly once.
    """

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

    async def transition(self, handoff_id: str, state: HandoffState) -> bool:
        """As the in-memory twin, except that ``fail_settle`` refuses that state exactly once.

        One transient hiccup on the write that ends a handoff, which is the failure that used to
        strand the store's active pointer: the settling state never lands, so nothing releases
        the claim the READY write took.
        """
        if state is self._fail_settle:
            self._fail_settle = None
            msg = f"redis refused the {state.value} write"
            raise HandoffStoreError(msg)
        return await super().transition(handoff_id, state)

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
    """The deep model's scripted stream: some text, optionally paused or killed mid-flight.

    ``tool_calls`` are asked for one per round before the text arrives, which is what lets a
    test watch the budget the deep phase resumed spend down across rounds. ``closed`` records
    that this generator was actually finalized, so a test can tell a stream that was torn down
    deterministically from one abandoned to the garbage collector.
    """

    def __init__(
        self,
        *,
        chunks: Sequence[str] = ("a deep ", "answer"),
        gate: Gate | None = None,
        gate_after: int = 1,
        fail_after: int | None = None,
        tool_calls: Sequence[ToolCall] = (),
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

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del tools, schema
        self.calls += 1
        self.models.append(model)
        self.seen = list(messages)
        if self.calls <= len(self._tool_calls):
            # A round asking for a tool, with the reply on whichever round runs out of them.
            yield self._tool_calls[self.calls - 1]
            return
        try:
            for index, chunk in enumerate(self._chunks):
                if self._fail_after is not None and index == self._fail_after:
                    msg = "the deep model's server died mid-stream"
                    raise InferenceError(msg)
                if self._gate is not None and index == self._gate_after:
                    await self._gate.pause()
                yield TextChunk(chunk)
        finally:
            self.closed = True


def request() -> PlacementRequest:
    """One subagent admission, for asserting that the pool admits again after a handoff."""
    return PlacementRequest("subagent", vram_gb=1.0, cpus=1.0, memory_gb=1.0)


def plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "drain_timeout_s": 60.0,
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def armed_slot(
    *,
    brief: str = BRIEF,
    taint: TaintLedger | None = None,
    tail: Sequence[Message] = (),
    budget: DispatchBudget | None = None,
) -> EscalationSlot:
    """A slot as the engine leaves it at the loop boundary: armed, filled, tail captured."""
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
    """The four outermost adapters a test may script; anything left out gets a plain one."""

    host: ScriptedModelHost | None = None
    handoffs: RecordingHandoffStore | None = None
    sessions: RecordingSessionStore | None = None
    backend: ScriptedBrainBackend | None = None


def recaller() -> MemoryRecaller:
    """The durable half of "the stores are intact": a real recaller over in-memory adapters.

    Wired into every harness by default, because a ``TurnCapabilities`` without memory makes
    the deep phase's memory write a no-op and the invariant it is supposed to cover vacuous.
    """
    minted = 0

    def next_id() -> str:
        nonlocal minted
        minted += 1
        return f"m{minted}"

    return MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), TickingClock(), id_factory=next_id)


@dataclass(slots=True)
class Harness:
    """One fully composed handoff, plus the fakes a test scripts and asserts against."""

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
        """Snapshot the machine behind a status the instant it crosses, and pass the event on.

        Every collector calls this, so no case can quietly opt out of the witness. Taken here
        rather than inside the conductor because the point is to read what the code under test
        did, from outside it.
        """
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
        """Every exchange this handoff wrote to durable memory, recalled back out of it."""
        hits = await self.memory.recall(USER_TEXT, k=5, session_id=SESSION)
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
    # Memory is wired in whatever else a test scripts, so "the stores are intact" covers the
    # durable store too; a caller's own capabilities keep everything but that.
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
    """Drive one handoff to the end, collecting every event it put on the turn's stream."""
    events: list[TurnEvent] = []
    stream = harness.conductor.run_handoff(slot, session_id=SESSION, turn_id=turn_id)
    try:
        async for event in stream:
            events.append(harness.observe(event))  # noqa: PERF401 - one event at a time
    finally:
        await stream.aclose()
    return events


def assert_the_window_announced_real_progress(live: Harness) -> None:
    """Every swap-window status, checked against the work IT announces (ADR-0030 decision 6).

    The order among the four details is the weaker half and it is asserted first: a handoff that
    stopped early says less, never something else. The half that matters is below it, because
    four strings in the right order relative to each other are satisfied by four strings emitted
    at any four moments, and three of them assert facts about the GPU that only a witness taken
    at the yield can check. So each status is pinned to the state of the machine when it
    crossed: announced work must not have happened yet, and claimed work must already have.

    Reads ``live.statuses``, which is one handoff's window (every caller asserts a handoff before
    running another on the same harness).
    """
    seen = [witness.detail for witness in live.statuses]
    assert seen == SWAP_WINDOW[: len(seen)]
    for witness in live.statuses:
        _WINDOW_CHECKS[witness.detail](live, witness)


def _draining_was_true(live: Harness, seen: StatusWitness) -> None:
    """ "Quiescing the subagent pool": said before the quiescing, with the record already safe."""
    del live  # this boundary is witnessed entirely by the snapshot
    assert seen.drains == 0  # announced ahead of the drain it names, not after it
    assert seen.host_ops == ()  # and nothing is evicted while subagents are still finishing
    assert seen.record_states[-1] is HandoffState.READY
    assert seen.deep_calls == 0


def _loading_was_true(live: Harness, seen: StatusWitness) -> None:
    """ "Loading the deep model": said once the pool is quiet and before the model is loaded."""
    assert seen.drains == (1 if live.pooled else 0)
    assert ("start", live.residency.brain_model) not in seen.host_ops
    assert ("stop", live.residency.cortex_model) not in seen.host_ops
    assert seen.record_states[-1] is HandoffState.READY


def _working_was_true(live: Harness, seen: StatusWitness) -> None:
    """ "The deep model is working on this": the one claim about the GPU, so witnessed hardest."""
    assert ("start", live.residency.brain_model) in seen.host_ops
    assert ("status", live.residency.brain_model) in seen.host_ops  # it health-gated, too
    assert seen.record_states[-1] is HandoffState.BRAIN_ACTIVE
    assert seen.deep_calls == 0  # about to work; a claim of work already done would be a lie


def _restoring_was_true(live: Harness, seen: StatusWitness) -> None:
    """ "Restoring the usual assistant": said after the deep model ran and before it is stopped."""
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
