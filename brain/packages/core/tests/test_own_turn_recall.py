from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import count

import swap_harness as harness
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    BrainPhase,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    Message,
    RecordingRecallSink,
    Role,
    SystemClock,
    TaintLedger,
    TextDelta,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.memory import MemoryRecord
from cortex_core.recall import MemoryRecaller
from cortex_core.turn_output import record_exchange

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
_ROW_TEXT = f"User: {harness.USER_TEXT}\nAssistant: {harness.CORTEX_TEXT}"


class _Embedder:
    async def embed(self, text: str) -> Sequence[float]:
        del text
        return (1.0, 0.0)


def _row(row_id: str, embedding: tuple[float, float] = (1.0, 0.0)) -> MemoryRecord:
    return MemoryRecord(
        id=row_id, text=_ROW_TEXT, embedding=embedding, at=_AT, session_id=harness.SESSION
    )


async def _seeded(*rows: MemoryRecord) -> tuple[MemoryRecaller, RecordingRecallSink]:
    store = InMemoryMemoryStore()
    for row in rows:
        await store.add(row)
    sink = RecordingRecallSink()
    return MemoryRecaller(store, _Embedder(), SystemClock(), audit=sink), sink


async def _recalled_ids(recaller: MemoryRecaller, leave_out: tuple[str, ...]) -> list[str]:
    hits = await recaller.recall(
        harness.USER_TEXT, k=5, session_id=harness.SESSION, turn_id="t", leave_out=leave_out
    )
    return [hit.record.id for hit in hits]


async def test_recall_leaves_out_a_named_row_and_keeps_an_earlier_row_with_the_same_text() -> None:
    recaller, sink = await _seeded(_row("own"), _row("earlier"))
    assert await _recalled_ids(recaller, ("own",)) == ["earlier"]
    (audit,) = sink.audits
    assert audit.pool_size == 1


async def test_recall_with_nothing_to_leave_out_finds_both_rows() -> None:
    recaller, _sink = await _seeded(_row("own"), _row("earlier"))
    assert sorted(await _recalled_ids(recaller, ())) == ["earlier", "own"]


async def test_a_left_out_row_gives_its_place_in_the_pool_to_the_next_nearest() -> None:
    recaller, sink = await _seeded(_row("own"), _row("earlier", (0.6, 0.8)))
    hits = await recaller.recall(
        harness.USER_TEXT, k=1, session_id=harness.SESSION, turn_id="t", leave_out=("own",)
    )
    assert [hit.record.id for hit in hits] == ["earlier"]
    assert sink.audits[0].pool_size == 1


async def test_a_left_out_id_no_row_holds_keeps_the_pool_at_its_size() -> None:
    recaller, sink = await _seeded(_row("near"), _row("far", (0.6, 0.8)))
    hits = await recaller.recall(
        harness.USER_TEXT, k=1, session_id=harness.SESSION, turn_id="t", leave_out=("gone",)
    )
    assert [hit.record.id for hit in hits] == ["near"]
    assert sink.audits[0].pool_size == 1


async def test_the_row_a_turn_stores_is_named_in_its_ledger() -> None:
    store = InMemoryMemoryStore()
    recaller = MemoryRecaller(store, _Embedder(), SystemClock(), id_factory=lambda: "own")
    taint = TaintLedger()
    await record_exchange(
        TurnCapabilities(memory=recaller),
        taint,
        store=InMemorySessionStore(),
        session_id=harness.SESSION,
        query=harness.USER_TEXT,
        reply=harness.CORTEX_TEXT,
        runs=(),
    )
    assert taint.written_ids == ("own",)


async def test_a_row_the_store_refused_is_not_named_in_the_ledger() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), _Embedder(), SystemClock())
    taint = TaintLedger(recalled_ids=("forgotten",))
    await record_exchange(
        TurnCapabilities(memory=recaller),
        taint,
        store=InMemorySessionStore(),
        session_id=harness.SESSION,
        query=harness.USER_TEXT,
        reply=harness.CORTEX_TEXT,
        runs=(),
    )
    assert taint.written_ids == ()


async def test_the_written_ids_survive_the_snapshot_into_the_deep_phases_ledger() -> None:
    taint = TaintLedger()
    taint.written_ids = ("own",)
    record = harness.prepared_slot(taint=taint).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    assert record.written_ids == ("own",)
    assert record.taint_ledger().written_ids == ("own",)


async def _deep_recall(written: tuple[str, ...]) -> list[str]:
    recaller, sink = await _seeded(_row("own"), _row("earlier"))
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=harness.USER_TEXT, at=_AT, turn_id=harness.TURN),
    )
    taint = TaintLedger()
    taint.written_ids = written
    record = harness.prepared_slot(taint=taint).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    phase = BrainPhase(
        sessions,
        ScriptedBrainBackend(),
        TickingClock(),
        "brain",
        TurnCapabilities(memory=recaller),
    )
    texts = [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    assert texts
    deep = sink.audits[0]
    assert deep.turn_id == harness.TURN
    return [scored.record.id for scored in deep.ranking.memories]


async def test_the_deep_phase_recalls_the_earlier_row_and_not_the_one_its_turn_wrote() -> None:
    assert await _deep_recall(("own",)) == ["earlier"]


async def test_a_deep_phase_whose_cortex_stored_no_row_recalls_both() -> None:
    assert sorted(await _deep_recall(())) == ["earlier", "own"]


async def test_a_later_turn_and_another_chat_recall_the_row_a_turn_wrote() -> None:
    minted = count(1)
    sink = RecordingRecallSink()
    recaller = MemoryRecaller(
        InMemoryMemoryStore(),
        HashEmbedder(),
        SystemClock(),
        audit=sink,
        id_factory=lambda: f"m{next(minted)}",
    )
    engine = TurnEngine(
        InMemorySessionStore(),
        ScriptedBrainBackend(),
        TickingClock(),
        capabilities=TurnCapabilities(memory=recaller),
    )
    for session_id, turn_id in ((harness.SESSION, "t-1"), (harness.SESSION, "t-2"), ("b", "t-3")):
        events = engine.handle_turn(session_id, harness.USER_TEXT, turn_id=turn_id)
        assert [event async for event in events]
    recalled = {a.turn_id: sorted(s.record.id for s in a.ranking.memories) for a in sink.audits}
    assert recalled == {"t-1": [], "t-2": ["m1"], "t-3": ["m1", "m2"]}
