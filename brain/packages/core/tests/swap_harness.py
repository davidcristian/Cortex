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
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cortex_core import (
    AdmitAllScheduler,
    DispatchBudget,
    EscalationRefs,
    EscalationSlot,
    HandoffRecord,
    HandoffState,
    InferenceError,
    InferenceEvent,
    InMemoryHandoffStore,
    InMemorySessionStore,
    JsonSchema,
    Message,
    PlacementRequest,
    RecordingSleeper,
    ResidencyPlan,
    Role,
    ScriptedModelHost,
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

SESSION = "s-handoff"
TURN = "t-handoff"
NONCE = "f00ddeadbeef0001"
USER_TEXT = "work out what is wrong with this proof"
CORTEX_TEXT = "handing this to the deep model"
BRIEF = "check the induction step; the base case holds"
CORTEX_URL = "http://llama-cortex:8080"
BRAIN_URL = "http://llama-brain:8081"
_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


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


class RecordingHandoffStore(InMemoryHandoffStore):
    """Records every state written, so a record that reached DONE and was deleted is provable.

    The store keeps only the latest record and a clean handoff deletes it at the end, so "the
    record reached a terminal state" is not observable from the final state alone. Every write
    lands in ``put`` (the in-memory transition rewrites through it), so recording there counts
    each state exactly once.
    """

    def __init__(self, *, put_gate: Gate | None = None, fail: Exception | None = None) -> None:
        super().__init__()
        self.states: list[HandoffState] = []
        self.deleted: list[str] = []
        self._put_gate = put_gate
        self._fail = fail

    async def put(self, record: HandoffRecord) -> None:
        if self._fail is not None:
            raise self._fail
        self.states.append(record.state)
        await super().put(record)
        if self._put_gate is not None:
            await self._put_gate.pause()

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
        tool_call: ToolCall | None = None,
    ) -> None:
        self.calls = 0
        self.seen: list[Message] = []
        self.models: list[str] = []
        self._chunks = list(chunks)
        self._gate = gate
        self._gate_after = gate_after
        self._fail_after = fail_after
        self._tool_call = tool_call

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
        if self._tool_call is not None and self.calls == 1:
            # One round asking for a tool, then the reply on the next: enough to watch what the
            # deep phase's dispatcher does with the budget it resumed.
            yield self._tool_call
            return
        for index, chunk in enumerate(self._chunks):
            if self._fail_after is not None and index == self._fail_after:
                msg = "the deep model's server died mid-stream"
                raise InferenceError(msg)
            if self._gate is not None and index == self._gate_after:
                await self._gate.pause()
            yield TextChunk(chunk)


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


@dataclass(slots=True)
class Harness:
    """One fully composed handoff, plus the fakes a test scripts and asserts against."""

    host: ScriptedModelHost
    manager: SwappingModelManager
    handoffs: RecordingHandoffStore
    sessions: RecordingSessionStore
    scheduler: AdmitAllScheduler
    backend: ScriptedBrainBackend
    conductor: SwapConductor
    residency: ResidencyPlan

    async def seed_session(self) -> None:
        """Persist what the cortex phase already persisted before it escalated."""
        await self.sessions.append(
            SESSION, Message(role=Role.USER, text=USER_TEXT, at=_AT, turn_id=TURN)
        )
        await self.sessions.append(
            SESSION, Message(role=Role.ASSISTANT, text=CORTEX_TEXT, at=_AT, turn_id=TURN)
        )


def build_harness(
    fakes: Fakes | None = None,
    *,
    residency: ResidencyPlan | None = None,
    capabilities: TurnCapabilities | None = None,
    scheduler: AdmitAllScheduler | None = None,
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
    pool = scheduler if scheduler is not None else AdmitAllScheduler()
    caps = capabilities if capabilities is not None else TurnCapabilities()
    return Harness(
        host=used_host,
        manager=manager,
        handoffs=used_handoffs,
        sessions=used_sessions,
        scheduler=pool,
        backend=used_backend,
        residency=used_plan,
        conductor=SwapConductor(
            used_handoffs,
            manager,
            BrainPhase(used_sessions, used_backend, clock, used_plan.brain_model, caps),
            used_plan,
            clock,
            pool if with_scheduler else None,
        ),
    )


async def run_handoff(harness: Harness, slot: EscalationSlot) -> list[TurnEvent]:
    """Drive one handoff to the end, collecting every event it put on the turn's stream."""
    events: list[TurnEvent] = []
    stream = harness.conductor.run_handoff(slot, session_id=SESSION, turn_id=TURN)
    try:
        async for event in stream:
            events.append(event)  # noqa: PERF401 - a bounded stream, read one event at a time
    finally:
        await stream.aclose()
    return events
