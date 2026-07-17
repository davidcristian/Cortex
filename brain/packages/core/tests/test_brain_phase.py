"""The deep model's phase: what it rebuilds from the stores, and what it leaves behind.

This is the one hard rule at its narrowest. The phase is handed nothing but a record and its
ports, so every assertion here is about state that came back out of a store or the record after
the process that produced it is (notionally) gone.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- dropping the record's ``loop_tail`` from the working set reddens
  ``test_the_deep_model_sees_the_history_and_the_tool_loop_tail_it_never_persisted``;
- rebuilding a fresh ``TaintLedger`` instead of the record's reddens
  ``test_a_tainted_turn_stays_tainted_and_keeps_its_laundering_evidence``;
- reusing a fresh ``DispatchBudget`` instead of resuming the carried position reddens
  ``test_the_carried_budget_bounds_the_deep_phase_too``;
- taking the query from the brief rather than from history reddens
  ``test_the_query_is_recovered_from_the_store_for_recall_and_memory``.
"""

from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    BRAIN_FAILED_NOTE,
    BUDGET_EXHAUSTED_MSG,
    DispatchBudget,
    InferenceError,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    SourceKind,
    SystemClock,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEvent,
    UrlRedactingGuardrail,
    as_source,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.memory import MemoryRecord
from cortex_core.recall import MemoryRecaller

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


async def _collect(events: AsyncGenerator[TurnEvent, None], into: list[str]) -> None:
    """Drain a phase's events into ``into``, letting whatever it raises propagate."""
    async for event in events:
        if isinstance(event, TextDelta):
            into.append(event.text)  # noqa: PERF401 - a live stream, read one event at a time


async def _drive(
    *,
    capabilities: TurnCapabilities | None = None,
    backend: ScriptedBrainBackend | None = None,
    tail: Sequence[Message] = (),
    taint: TaintLedger | None = None,
    store: InMemorySessionStore | None = None,
) -> tuple[BrainPhase, ScriptedBrainBackend, InMemorySessionStore, list[str]]:
    """Run one deep phase over a seeded session, returning what it saw and what it streamed."""
    sessions = store if store is not None else InMemorySessionStore()
    if store is None:
        await sessions.append(
            harness.SESSION,
            Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
        )
        await sessions.append(
            harness.SESSION,
            Message(role=Role.ASSISTANT, text=harness.CORTEX_TEXT, at=_AT, turn_id=harness.TURN),
        )
    used_backend = backend if backend is not None else ScriptedBrainBackend()
    phase = BrainPhase(
        sessions,
        used_backend,
        TickingClock(),
        "brain",
        capabilities if capabilities is not None else TurnCapabilities(),
    )
    slot = harness.armed_slot(tail=tail, taint=taint)
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    texts: list[str] = []
    events = phase.run(record)
    try:
        await _collect(events, texts)
    finally:
        await events.aclose()
    return phase, used_backend, sessions, texts


async def test_the_deep_model_sees_the_history_and_the_tool_loop_tail_it_never_persisted() -> None:
    """Preamble plus history plus the tail: the turn continues where the cortex left it."""
    tail = (
        Message(
            role=Role.ASSISTANT,
            text="",
            at=_AT,
            turn_id=harness.TURN,
            tool_calls=(ToolCall(id="c1", name="escalate_to_brain", arguments={"brief": "go"}),),
        ),
        Message(role=Role.TOOL, text="queued", at=_AT, turn_id=harness.TURN, tool_call_id="c1"),
    )
    _phase, backend, _sessions, _deltas = await _drive(tail=tail)
    seen = [(message.role, message.text) for message in backend.seen]
    assert (Role.USER, harness.USER_TEXT) in seen
    assert (Role.ASSISTANT, harness.CORTEX_TEXT) in seen
    # The tail comes last, in order, with the escalating call itself carrying the brief.
    assert [message.role for message in backend.seen[-2:]] == [Role.ASSISTANT, Role.TOOL]
    assert backend.seen[-2].tool_calls[0].arguments == {"brief": "go"}


async def test_a_tainted_turn_stays_tainted_and_keeps_its_laundering_evidence() -> None:
    """Taint that did not survive the swap would fail open, and the URL set is the defense."""
    ledger = TaintLedger()
    ledger.ingest_untrusted(
        "read http://evil.test/x", source=as_source(SourceKind.TOOL, "read_page")
    )
    backend = ScriptedBrainBackend(chunks=("visit http://evil.test/x now",))
    _phase, _backend, _sessions, texts = await _drive(
        backend=backend,
        taint=ledger,
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    # The guardrail opened over the RECORD's evidence, so the laundered URL is scrubbed from
    # the deep model's reply exactly as it would have been from the cortex's.
    assert "http://evil.test/x" not in "".join(texts)


async def test_a_tainted_turn_is_kept_out_of_memory_by_the_same_policy() -> None:
    """One taint policy, applied by both phases: the default drops a tainted exchange."""
    ledger = TaintLedger()
    ledger.ingest_untrusted("untrusted", source=None)
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(
        taint=ledger, capabilities=TurnCapabilities(memory=memory)
    )
    assert await _recorded(memory) == []
    # With the recording policy on, it is remembered instead, marked untrusted.
    memory_on = _recaller()
    _phase2, _backend2, _sessions2, _texts2 = await _drive(
        taint=ledger,
        capabilities=TurnCapabilities(memory=memory_on, record_tainted_memory=True),
    )
    recorded = await _recorded(memory_on)
    assert len(recorded) == 1
    assert recorded[0].tainted is True


async def test_the_untainted_exchange_is_remembered_as_the_turn_it_was() -> None:
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(capabilities=TurnCapabilities(memory=memory))
    (record,) = await _recorded(memory)
    assert record.text == f"User: {harness.USER_TEXT}\nAssistant: a deep answer"
    assert record.tainted is False


async def test_the_carried_budget_bounds_the_deep_phase_too() -> None:
    """A swap must not refill the turn's allowance: the deep model gets what was left."""
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(_registry(), audit, SystemClock())
    backend = ScriptedBrainBackend(
        chunks=("done",), tool_call=ToolCall(id="c1", name="read", arguments={})
    )
    slot = harness.armed_slot(budget=_spent_budget())
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    assert record.budget_closed is True  # the cortex phase had already exhausted the pool
    sessions = InMemorySessionStore()
    phase = BrainPhase(
        sessions, backend, TickingClock(), "brain", TurnCapabilities(tools=dispatcher)
    )
    events = phase.run(record)
    try:
        async for _event in events:
            pass
    finally:
        await events.aclose()
    # The pool arrived closed, so the deep model's tool call is refused and audited rather than
    # running on a fresh allowance.
    (invocation,) = audit.records
    assert invocation.ok is False
    assert invocation.detail == BUDGET_EXHAUSTED_MSG


async def test_the_query_is_recovered_from_the_store_for_recall_and_memory() -> None:
    """The record carries no user text, so the query comes back out of the session store."""
    memory = _recaller()
    _phase, _backend, _sessions, _texts = await _drive(capabilities=TurnCapabilities(memory=memory))
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.USER_TEXT}")


async def test_a_session_deleted_mid_handoff_falls_back_to_the_brief() -> None:
    """With no user message left to read, the cortex's brief is the truest ask available."""
    memory = _recaller()
    empty = InMemorySessionStore()
    _phase, _backend, _sessions, _texts = await _drive(
        store=empty, capabilities=TurnCapabilities(memory=memory)
    )
    (recorded,) = await _recorded(memory)
    assert recorded.text.startswith(f"User: {harness.BRIEF}")


async def test_a_deep_model_that_dies_releases_what_the_guardrail_still_held() -> None:
    """A death mid-stream still flushes the guarded carry, so no shown text is lost silently."""
    backend = ScriptedBrainBackend(chunks=("see http://exa", "never streamed"), fail_after=1)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        sessions,
        backend,
        TickingClock(),
        "brain",
        TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    record = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    collected: list[str] = []
    with pytest.raises(InferenceError):
        await _collect(events, collected)
    await events.aclose()
    # The partial URL the filter was still holding is released before the note, and persisted.
    assert "".join(collected) == "see http://exa" + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await sessions.history(harness.SESSION)]
    assert persisted[-1] == "see http://exa" + BRAIN_FAILED_NOTE


async def test_a_deep_model_that_dies_persists_its_partial_text_with_the_note() -> None:
    backend = ScriptedBrainBackend(chunks=("half an ", "never streamed"), fail_after=1)
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(sessions, backend, TickingClock(), "brain", TurnCapabilities())
    slot = harness.armed_slot()
    record = slot.snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    events = phase.run(record)
    collected: list[str] = []
    # The phase re-raises after persisting, so the conductor can fail the record and converge.
    with pytest.raises(InferenceError, match="died mid-stream"):
        await _collect(events, collected)
    await events.aclose()
    assert "".join(collected) == "half an " + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await sessions.history(harness.SESSION)]
    assert persisted[-1] == "half an " + BRAIN_FAILED_NOTE


def _spent_budget() -> DispatchBudget:
    budget = DispatchBudget(limit=1)
    assert budget.charge(2) is False  # closes the pool for good
    return budget


def _registry() -> InMemoryToolRegistry:
    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        return "ok"

    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a thing", parameters={}), handler)}
    )


def _recaller() -> MemoryRecaller:
    return MemoryRecaller(
        InMemoryMemoryStore(), _Embedder(), SystemClock(), id_factory=lambda: "m1"
    )


async def _recorded(recaller: MemoryRecaller) -> list[MemoryRecord]:
    hits = await recaller.recall("anything", k=5, session_id=harness.SESSION)
    return [hit.record for hit in hits]


class _Embedder:
    async def embed(self, text: str) -> Sequence[float]:
        del text
        return (1.0, 0.0)
