"""Shared HandoffStore behavior checks. Every implementation must pass all of them."""

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
    ImagePart,
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


def opaque_ledger() -> TaintLedger:
    """The same ledger plus the unfenceable bit, set the one way production sets it."""
    ledger = tainted_ledger()
    ledger.observe(
        ToolResult(
            call_id="c2",
            content="screen capture of the primary display",
            trust=Trust.UNTRUSTED,
            images=(ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8),),
        ),
        source=Provenance(kind=SourceKind.TOOL, value="capture_screen"),
    )
    return ledger


def make_record(
    handoff_id: str,
    *,
    state: HandoffState = HandoffState.READY,
    requested_at: datetime = _AT,
    opaque: bool = False,
) -> HandoffRecord:
    """One full-shape record, snapshotted off a live slot exactly as the conductor will."""
    ledger = opaque_ledger() if opaque else tainted_ledger()
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
    """The taint bit, the source order, the kinds and the URL set all survive a round trip."""
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


async def check_the_opaque_bit_round_trips_both_ways(store: HandoffStore) -> None:
    """The unfenceable-content bit survives the store, both set and unset."""
    clean = make_record(_handoff_id())
    assert clean.opaque is False
    await store.put(clean)
    loaded_clean = await store.get(clean.handoff_id)
    assert loaded_clean is not None
    assert loaded_clean.opaque is False
    assert loaded_clean.taint_ledger().opaque is False
    await store.delete(clean.handoff_id)

    record = make_record(_handoff_id(), opaque=True)
    assert record.opaque is True
    await store.put(record)
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded == record
    assert loaded.opaque is True
    restored = loaded.taint_ledger()
    assert restored.opaque is True
    assert restored == opaque_ledger()
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


async def check_the_settled_reason_outlives_the_process(store: HandoffStore) -> None:
    """A ``FAILED`` record says why, and it says it from the store rather than from an object."""
    reason = (
        "the model host failed while swapping in 'brain': the model host refused POST "
        '/models/cortex/stop for model \'cortex\' with HTTP 503: {"detail": "child is wedged"}'
    )
    record = make_record(_handoff_id())
    await store.put(record)
    assert record.failure is None
    assert await store.transition(record.handoff_id, HandoffState.FAILED, failure=reason) is True
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded.state is HandoffState.FAILED
    assert loaded.failure == reason
    await store.delete(record.handoff_id)


async def check_a_reasonless_transition_leaves_no_reason_behind(store: HandoffStore) -> None:
    """A state written without a reason has none, whatever the record said before."""
    record = make_record(_handoff_id())
    await store.put(record)
    assert await store.transition(record.handoff_id, HandoffState.FAILED, failure="a bad swap")
    assert await store.transition(record.handoff_id, HandoffState.DONE) is True
    loaded = await store.get(record.handoff_id)
    assert loaded is not None
    assert loaded.state is HandoffState.DONE
    assert loaded.failure is None
    await store.delete(record.handoff_id)


async def check_delete_removes_and_releases(store: HandoffStore) -> None:
    """Delete removes the record and the active slot it held; deleting again is a no-op."""
    record = make_record(_handoff_id())
    await store.put(record)
    await store.delete(record.handoff_id)
    assert await store.get(record.handoff_id) is None
    assert await store.active() is None
    await store.delete(record.handoff_id)


async def check_a_terminal_put_is_never_active(store: HandoffStore) -> None:
    """Persisting an already-terminal record leaves the active slot empty."""
    record = make_record(_handoff_id(), state=HandoffState.FAILED)
    await store.put(record)
    assert await store.active() is None
    assert await store.get(record.handoff_id) == record
    await store.delete(record.handoff_id)


async def check_the_last_nonterminal_put_wins_the_slot(store: HandoffStore) -> None:
    """The pointer follows the newest in-flight record; deleting another leaves it alone."""
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
    check_the_opaque_bit_round_trips_both_ways,
    check_put_claims_the_active_slot,
    check_transition_walks_the_lifecycle,
    check_terminal_transition_releases_active_but_keeps_the_record,
    check_transition_of_an_unknown_id_is_false,
    check_the_settled_reason_outlives_the_process,
    check_a_reasonless_transition_leaves_no_reason_behind,
    check_delete_removes_and_releases,
    check_a_terminal_put_is_never_active,
    check_the_last_nonterminal_put_wins_the_slot,
    check_timezone_fidelity,
)
