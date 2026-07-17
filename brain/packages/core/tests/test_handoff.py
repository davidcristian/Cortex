"""The handoff record and escalation slot: pure value behavior (ADR-0030 decision 2).

The store-facing round trip lives in the session package's contract suite; here the value
semantics are pinned: what a snapshot captures (and from where), what it refuses, and that
the reconstructed ledger is exact and detached from the record.
"""

from datetime import UTC, datetime

import pytest

from cortex_core import (
    DispatchBudget,
    EscalationRefs,
    EscalationSlot,
    HandoffRecord,
    HandoffState,
    Message,
    Provenance,
    Role,
    SourceKind,
    TaintLedger,
    ToolCall,
)

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _ledger() -> TaintLedger:
    return TaintLedger(
        tainted=True,
        untrusted_urls={"http://evil.example/a"},
        sources=(Provenance(kind=SourceKind.SENDER, value="mallory@evil.example"),),
    )


def _slot(working: list[Message], *, budget: DispatchBudget, base_len: int) -> EscalationSlot:
    return EscalationSlot(
        refs=EscalationRefs(
            working=working,
            taint=_ledger(),
            nonce="cafe0123beef4567",
            budget=budget,
            base_len=base_len,
        ),
        brief="go deep on this",
    )


def _tail(turn_id: str) -> list[Message]:
    call = ToolCall(id="c1", name="read_file", arguments={"path": "notes.md"})
    return [
        Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=turn_id, tool_calls=(call,)),
        Message(role=Role.TOOL, text="fenced", at=_AT, turn_id=turn_id, tool_call_id="c1"),
    ]


def test_requested_at_must_be_timezone_aware() -> None:
    naive = datetime(2026, 7, 25, 12, 0)  # noqa: DTZ001 - the rejected input is the point
    with pytest.raises(ValueError, match="timezone-aware"):
        _slot([], budget=DispatchBudget(), base_len=0).snapshot(
            turn_id="t1", session_id="s1", requested_at=naive
        )


def test_terminal_is_exactly_done_and_failed() -> None:
    assert HandoffState.DONE.terminal
    assert HandoffState.FAILED.terminal
    assert not HandoffState.PENDING.terminal
    assert not HandoffState.READY.terminal
    assert not HandoffState.BRAIN_ACTIVE.terminal


def test_snapshot_captures_the_loop_tail_and_derives_rounds_from_it() -> None:
    user = Message(role=Role.USER, text="hi", at=_AT, turn_id="t1")
    tail = _tail("t1")
    budget = DispatchBudget(limit=10)
    budget.charge(4)
    slot = _slot([user, *tail], budget=budget, base_len=1)
    record = slot.snapshot(turn_id="t1", session_id="s1", requested_at=_AT)
    assert record.state is HandoffState.READY
    assert (record.handoff_id, record.session_id) == ("t1", "s1")
    assert (record.brief, record.nonce) == ("go deep on this", "cafe0123beef4567")
    assert record.loop_tail == tuple(tail)  # the user message before base_len is NOT carried
    assert record.rounds_used == 1  # one assistant tool-call message = one dispatched round
    assert (record.budget_remaining, record.budget_closed) == (6, False)
    assert record.tainted is True
    assert record.sources == _ledger().sources
    assert record.untrusted_urls == frozenset({"http://evil.example/a"})


def test_snapshot_carries_a_closed_budget_as_closed() -> None:
    budget = DispatchBudget(limit=2)
    assert budget.charge(3) is False  # closes the pool without spending
    record = _slot([], budget=budget, base_len=0).snapshot(
        turn_id="t1", session_id="s1", requested_at=_AT
    )
    assert (record.budget_remaining, record.budget_closed) == (2, True)
    assert record.rounds_used == 0
    assert record.loop_tail == ()


def test_snapshot_without_a_brief_is_a_caller_bug() -> None:
    slot = _slot([], budget=DispatchBudget(), base_len=0)
    slot.brief = None
    with pytest.raises(ValueError, match="requires a brief"):
        slot.snapshot(turn_id="t1", session_id="s1", requested_at=_AT)


def test_snapshot_of_an_unarmed_slot_is_a_caller_bug() -> None:
    # The wrapper builds the slot empty and the engine arms it at turn start (ADR-0030
    # decision 5); a snapshot before any turn armed it has no state to serialize.
    slot = EscalationSlot(brief="go deep on this")
    with pytest.raises(ValueError, match="armed"):
        slot.snapshot(turn_id="t1", session_id="s1", requested_at=_AT)


def test_snapshot_detaches_from_the_live_ledger_and_working_list() -> None:
    ledger = _ledger()
    working = [*_tail("t1")]
    slot = EscalationSlot(
        refs=EscalationRefs(
            working=working,
            taint=ledger,
            nonce="cafe0123beef4567",
            budget=DispatchBudget(),
            base_len=0,
        ),
        brief="go",
    )
    record = slot.snapshot(turn_id="t1", session_id="s1", requested_at=_AT)
    ledger.untrusted_urls.add("http://evil.example/later")
    working.append(Message(role=Role.TOOL, text="late", at=_AT, turn_id="t1", tool_call_id="c9"))
    assert record.untrusted_urls == frozenset({"http://evil.example/a"})
    assert len(record.loop_tail) == 2


def test_taint_ledger_reconstruction_is_exact_and_detached() -> None:
    ledger = _ledger()
    record = HandoffRecord(
        handoff_id="t1",
        session_id="s1",
        requested_at=_AT,
        state=HandoffState.READY,
        brief="go",
        nonce="cafe0123beef4567",
        tainted=ledger.tainted,
        sources=ledger.sources,
        untrusted_urls=frozenset(ledger.untrusted_urls),
        budget_remaining=5,
        budget_closed=False,
        rounds_used=0,
        loop_tail=(),
    )
    restored = record.taint_ledger()
    assert restored == ledger
    restored.untrusted_urls.add("http://evil.example/later")
    assert record.untrusted_urls == frozenset({"http://evil.example/a"})
