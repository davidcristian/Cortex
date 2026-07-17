"""Shared HandoffStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract test (in-memory fake + fakeredis-backed Redis adapter).
The two must be observably interchangeable behind the port (ports-before-adapters, ADR-0030).
The load-bearing check is the tainted-ledger round trip: a ledger built through the REAL
``TaintLedger`` API (an observed untrusted result with a claimed sender, plus ingested
untrusted content naming a URI and a memory) must come back from the store bit-, order-, and
set-exact, or taint would fail open across the model swap.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import (
    DispatchBudget,
    EscalationRefs,
    EscalationSlot,
    HandoffRecord,
    HandoffState,
    HandoffStore,
    Message,
    Provenance,
    Role,
    SourceKind,
    TaintLedger,
    ToolCall,
    ToolResult,
    Trust,
    wrap_untrusted,
)

_AT = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)
_NONCE = "f00ddeadbeef0001"


def _handoff_id() -> str:
    return f"contract-{uuid4()}"


def tainted_ledger() -> TaintLedger:
    """A ledger built through the real API: tainted, four sources (both trust halves), URLs."""
    ledger = TaintLedger()
    ledger.observe(
        ToolResult(
            call_id="c1",
            content="From: Mallory. Full report at http://evil.example/report today.",
            trust=Trust.UNTRUSTED,
            source=Provenance(kind=SourceKind.SENDER, value="Mallory <mallory@evil.example>"),
        ),
        source=Provenance(kind=SourceKind.TOOL, value="read_email"),
    )
    ledger.ingest_untrusted(
        "recalled note citing http://evil.example/note",
        source=Provenance(kind=SourceKind.URI, value="http://evil.example/note"),
    )
    ledger.ingest_untrusted(
        "a stored tainted memory", source=Provenance(kind=SourceKind.MEMORY, value="mem-42")
    )
    return ledger


def make_record(
    handoff_id: str,
    *,
    state: HandoffState = HandoffState.READY,
    requested_at: datetime = _AT,
) -> HandoffRecord:
    """One full-shape record, snapshotted off a live slot exactly as the conductor will."""
    ledger = tainted_ledger()
    budget = DispatchBudget(limit=8)
    budget.charge(3)
    call = ToolCall(id="c1", name="read_email", arguments={"folder": "inbox", "limit": 2})
    working = [
        Message(role=Role.USER, text="dig into this thread", at=requested_at, turn_id=handoff_id),
        Message(
            role=Role.ASSISTANT,
            text="",
            at=requested_at,
            turn_id=handoff_id,
            tool_calls=(call,),
        ),
        Message(
            role=Role.TOOL,
            text=wrap_untrusted("Full report at http://evil.example/report", nonce=_NONCE),
            at=requested_at,
            turn_id=handoff_id,
            tool_call_id="c1",
        ),
    ]
    slot = EscalationSlot(
        refs=EscalationRefs(
            working=working,
            taint=ledger,
            nonce=_NONCE,
            budget=budget,
            base_len=1,
        ),
        brief="reason deeply over the mail thread; the sender's claims need checking",
    )
    record = slot.snapshot(
        turn_id=handoff_id, session_id=f"session-{handoff_id}", requested_at=requested_at
    )
    return record if state is HandoffState.READY else replace(record, state=state)


async def check_missing_reads_are_none(store: HandoffStore) -> None:
    """An unknown id reads back as None, and an empty store has no active handoff."""
    assert await store.get(_handoff_id()) is None
    assert await store.active() is None


async def check_record_round_trips_field_for_field(store: HandoffStore) -> None:
    """The whole record survives: brief, nonce, budget position, and the tool-bearing tail."""
    record = make_record(_handoff_id())
    await store.put(record)
    loaded = await store.get(record.handoff_id)
    assert loaded == record
    assert loaded is not None
    assert loaded.loop_tail[0].tool_calls[0].arguments == {"folder": "inbox", "limit": 2}
    assert loaded.loop_tail[1].tool_call_id == "c1"
    assert (loaded.budget_remaining, loaded.budget_closed, loaded.rounds_used) == (5, False, 1)
    await store.delete(record.handoff_id)


async def check_tainted_ledger_round_trips_exactly(store: HandoffStore) -> None:
    """THE pinned round trip (ADR-0030 decision 2): bit, sources order, kinds, URL set.

    A reconstructed ledger equal to the live one is what makes taint persistence across the
    swap real: the claimed sources stay claimed (inert quotations), the attested stay
    attested, in the order the turn read them, and every laundering-evidence URL survives.
    """
    ledger = tainted_ledger()
    record = make_record(_handoff_id())
    await store.put(record)
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    restored = loaded.taint_ledger()
    assert restored == ledger
    assert restored.tainted is True
    assert restored.sources == ledger.sources
    assert [source.kind for source in restored.sources] == [
        SourceKind.TOOL,
        SourceKind.SENDER,
        SourceKind.URI,
        SourceKind.MEMORY,
    ]
    assert [source.kind.attested for source in restored.sources] == [True, False, False, True]
    assert restored.untrusted_urls == ledger.untrusted_urls
    assert "http://evil.example/report" in restored.untrusted_urls
    await store.delete(record.handoff_id)


async def check_put_claims_the_active_slot(store: HandoffStore) -> None:
    """A non-terminal put becomes THE active handoff (at most one is in flight)."""
    record = make_record(_handoff_id())
    await store.put(record)
    assert await store.active() == record
    await store.delete(record.handoff_id)


async def check_transition_walks_the_lifecycle(store: HandoffStore) -> None:
    """A non-terminal transition rewrites the state and keeps the record active."""
    record = make_record(_handoff_id())
    await store.put(record)
    assert await store.transition(record.handoff_id, HandoffState.BRAIN_ACTIVE) is True
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded.state is HandoffState.BRAIN_ACTIVE
    assert await store.active() == loaded
    await store.delete(record.handoff_id)


async def check_terminal_transition_releases_active_but_keeps_the_record(
    store: HandoffStore,
) -> None:
    """DONE/FAILED ends the handoff: no longer active, still readable for diagnosis."""
    record = make_record(_handoff_id())
    await store.put(record)
    assert await store.transition(record.handoff_id, HandoffState.DONE) is True
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded.state is HandoffState.DONE
    assert await store.active() is None
    await store.delete(record.handoff_id)


async def check_transition_of_an_unknown_id_is_false(store: HandoffStore) -> None:
    """A transition on an unknown/expired id no-ops False, never an error."""
    assert await store.transition(_handoff_id(), HandoffState.FAILED) is False


async def check_delete_removes_and_releases(store: HandoffStore) -> None:
    """Delete removes the record and the active slot it held; deleting again is a no-op."""
    record = make_record(_handoff_id())
    await store.put(record)
    await store.delete(record.handoff_id)
    assert await store.get(record.handoff_id) is None
    assert await store.active() is None
    await store.delete(record.handoff_id)


async def check_a_terminal_put_is_never_active(store: HandoffStore) -> None:
    """Persisting an already-terminal record (boot recovery's write) claims nothing."""
    record = make_record(_handoff_id(), state=HandoffState.FAILED)
    await store.put(record)
    assert await store.active() is None
    assert await store.get(record.handoff_id) == record
    await store.delete(record.handoff_id)


async def check_the_last_nonterminal_put_wins_the_slot(store: HandoffStore) -> None:
    """The pointer follows the newest in-flight record; deleting another leaves it alone.

    The store does not referee concurrent handoffs (the conductor checks ``active()``
    before snapshotting, and it is the one writer); it only keeps the pointer coherent.
    """
    first = make_record(_handoff_id())
    second = make_record(_handoff_id())
    await store.put(first)
    await store.put(second)
    assert await store.active() == second
    await store.delete(first.handoff_id)
    assert await store.active() == second
    await store.delete(second.handoff_id)


async def check_timezone_fidelity(store: HandoffStore) -> None:
    """A non-UTC timestamp survives with its offset intact, on the record and its tail."""
    offset = timezone(timedelta(hours=5, minutes=30))
    at = datetime(2026, 7, 25, 17, 45, tzinfo=offset)
    record = make_record(_handoff_id(), requested_at=at)
    await store.put(record)
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded.requested_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert loaded.loop_tail[0].at.utcoffset() == timedelta(hours=5, minutes=30)
    await store.delete(record.handoff_id)


ALL_CHECKS = (
    check_missing_reads_are_none,
    check_record_round_trips_field_for_field,
    check_tainted_ledger_round_trips_exactly,
    check_put_claims_the_active_slot,
    check_transition_walks_the_lifecycle,
    check_terminal_transition_releases_active_but_keeps_the_record,
    check_transition_of_an_unknown_id_is_false,
    check_delete_removes_and_releases,
    check_a_terminal_put_is_never_active,
    check_the_last_nonterminal_put_wins_the_slot,
    check_timezone_fidelity,
)
