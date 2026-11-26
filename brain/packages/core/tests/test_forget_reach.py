from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    RecordingRecallSink,
    ScoredMemory,
    SystemClock,
    TaintLedger,
    TurnCapabilities,
)
from cortex_core.dispatch_round import ToolLoopContext
from cortex_core.forget_reach import FORGET_REACH_LIMIT, forget_reach, more_held_note
from cortex_core.ranking import RankBasis, RankedMemory, Ranking
from cortex_core.turn_context import assemble_inference_messages

_AT = datetime(2026, 11, 15, 3, 0, 0, tzinfo=UTC)
_CARD = "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted."
_GYM = "User: Remember that my gym code is 4242.\nAssistant: Noted."
_LOCKER = "User: Remember that my locker code is 4242.\nAssistant: Noted."
_PHONE = "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted."
_CAT = "User: Remember that my cat is called Miso.\nAssistant: Noted."


def _said(row: str) -> str:
    return row.partition("\n")[0]


class _CardOnly:
    def candidate_k(self, k: int) -> int:
        return k

    async def select(
        self,
        hits: Sequence[ScoredMemory],
        *,
        query: str,
        now: datetime,
        k: int,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Ranking:
        del query, now, k, session_id, turn_id
        kept = [hit for hit in hits if "card" in hit.record.text]
        return Ranking(
            hits=tuple(RankedMemory(hit=hit, key=hit.score) for hit in kept), basis=RankBasis.ECHO
        )


class _Counting(InMemoryMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        self.calls.append("search")
        return await super().search(embedding, k=k, scopes=scopes)

    async def find_value(
        self, value: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        self.calls.append(f"find_value {value}")
        return await super().find_value(value, limit=limit, scopes=scopes)


class _ValueFails(InMemoryMemoryStore):
    async def find_value(
        self, value: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        del value, limit, scopes
        msg = "the store is down"
        raise MemoryStoreError(msg)


async def _rig(
    store: InMemoryMemoryStore,
    *texts: str,
    tainted: Sequence[str] = (),
    audit: RecordingRecallSink | None = None,
) -> TurnCapabilities:
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(
            MemoryRecord(
                id=f"m{index}", text=text, embedding=embedding, at=_AT, tainted=text in tainted
            )
        )
    recaller = MemoryRecaller(store, HashEmbedder(), SystemClock(), policy=_CardOnly(), audit=audit)
    return TurnCapabilities(memory=recaller)


def _context(taint: TaintLedger | None = None) -> ToolLoopContext:
    return ToolLoopContext(
        dispatcher=None,
        clock=SystemClock(),
        turn_id="t",
        taint=taint or TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def _memory_text(caps: TurnCapabilities, query: str, taint: TaintLedger | None = None) -> str:
    messages = await assemble_inference_messages(query, [], caps, _context(taint), SystemClock())
    return "\n".join(message.text for message in messages[1:])


@pytest.mark.parametrize(
    "query",
    [
        "Forget all 4242 except the card.",
        "Forget all 4242 apart from the card.",
        "Forget all 4242, only the card.",
        "Forget 4242.",
    ],
)
async def test_a_forget_naming_a_value_holds_every_row_holding_it(query: str) -> None:
    caps = await _rig(InMemoryMemoryStore(), _LOCKER, _CARD, _PHONE, _CAT)

    text = await _memory_text(caps, query)

    assert [row for row in (_LOCKER, _CARD, _PHONE, _CAT) if _said(row) in text] == [
        _LOCKER,
        _CARD,
        _PHONE,
    ]


async def test_a_forget_of_everything_but_one_fact_holds_the_nearest_rows() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _GYM)

    text = await _memory_text(caps, "Forget everything but my card.")

    assert _said(_CARD) in text
    assert _said(_GYM) in text


async def test_a_forget_naming_no_value_and_no_fact_to_keep_adds_no_row() -> None:
    store = _Counting()
    caps = await _rig(store, _CARD, _GYM)

    text = await _memory_text(caps, "Forget my gym code.")

    assert _said(_GYM) not in text
    assert store.calls == ["search"]


@pytest.mark.parametrize(
    "query",
    [
        "Hello.",
        "What is my card number?",
        "Remember that my gym code is 4242.",
        "Don't forget my gym code is 4242.",
        "I always forget my card is 4111 1111 1111 4242.",
        "My code is 4242, not 4243.",
        "Delete my 9am reminder.",
    ],
)
async def test_a_message_asking_to_forget_nothing_reads_the_store_once(query: str) -> None:
    store = _Counting()
    caps = await _rig(store, _LOCKER, _CARD, _PHONE)

    text = await _memory_text(caps, query)

    assert store.calls == ["search"]
    assert _said(_LOCKER) not in text
    assert _said(_PHONE) not in text


async def test_a_ranked_row_the_forget_reaches_is_held_once() -> None:
    caps = await _rig(InMemoryMemoryStore(), _LOCKER, _CARD)

    text = await _memory_text(caps, "Forget all 4242 except the card.")

    assert text.count(_said(_CARD)) == 1
    assert text.index(_said(_CARD)) < text.index(_said(_LOCKER))


async def test_a_forget_adds_no_more_rows_than_its_limit() -> None:
    codes = [
        f"User: Remember that door {index} opens with 4242.\nAssistant: Noted."
        for index in range(8)
    ]
    caps = await _rig(InMemoryMemoryStore(), _CARD, *codes)

    text = await _memory_text(caps, "Forget all 4242 except the card.")

    assert sum(_said(code) in text for code in codes) == FORGET_REACH_LIMIT - 1
    assert text.count(_said(_CARD)) == 1


async def test_a_forget_naming_two_values_adds_no_more_rows_than_its_limit() -> None:
    doors = [
        f"User: Remember that door {index} opens with 4242.\nAssistant: Noted."
        for index in range(4)
    ]
    gates = [
        f"User: Remember that bay {index} opens with 5555.\nAssistant: Noted." for index in range(4)
    ]
    caps = await _rig(InMemoryMemoryStore(), *doors, *gates)

    text = await _memory_text(caps, "Forget 4242 and 5555.")

    assert sum(_said(row) in text for row in (*doors, *gates)) == FORGET_REACH_LIMIT


async def test_a_tainted_row_a_forget_reaches_is_quoted_as_untrusted_data() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _LOCKER, tainted=[_LOCKER])
    taint = TaintLedger()

    text = await _memory_text(caps, "Forget all 4242 except the card.", taint)

    fenced = text.split("<untrusted-tool-output id=n>")[1]
    assert "my locker code is 4242" in fenced
    assert "my card is" not in fenced
    assert taint.recalled_ids == ("m1",)


async def test_a_store_that_fails_while_reaching_answers_the_turn_without_memory() -> None:
    caps = await _rig(_ValueFails(), _CARD, _LOCKER)

    assert await _memory_text(caps, "Forget all 4242 except the card.") == ""


async def test_a_message_asking_to_forget_nothing_reaches_nothing() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _LOCKER)
    assert caps.memory is not None

    assert await forget_reach("What is my card?", caps.memory, session_id="s", ranked=5) is None


def _long_card(index: int) -> str:
    return f"User: Remember that card {index} {'is kept in the blue folder ' * 30}opens 4242."


async def test_a_value_past_the_cut_of_a_reached_row_is_not_in_the_request() -> None:
    rows = [_long_card(index) for index in range(12)]
    caps = await _rig(InMemoryMemoryStore(), *rows)

    text = await _memory_text(caps, "Forget 4242.")

    shown = text.count("Remember that card")
    assert shown > FORGET_REACH_LIMIT
    assert text.count("[memory cut here:") == shown
    assert "opens 4242." not in text
    assert text.endswith(more_held_note("4242"))


async def test_no_line_says_more_rows_hold_a_value_when_every_row_holding_it_is_shown() -> None:
    caps = await _rig(InMemoryMemoryStore(), _LOCKER, _CARD, _PHONE, _CAT)

    text = await _memory_text(caps, "Forget 4242.")

    assert _said(_LOCKER) in text
    assert more_held_note("4242") not in text


async def test_the_line_names_only_the_value_more_rows_hold_than_are_shown() -> None:
    doors = [
        f"User: Remember that door {index} opens with 4242.\nAssistant: Noted."
        for index in range(8)
    ]
    caps = await _rig(InMemoryMemoryStore(), _CARD, _CAT, *doors)

    text = await _memory_text(caps, "Forget 4242 and Miso, keep the card.")

    assert more_held_note("4242") in text
    assert more_held_note("Miso") not in text


async def test_the_recall_audit_holds_the_rows_the_forget_reached() -> None:
    audit = RecordingRecallSink()
    caps = await _rig(InMemoryMemoryStore(), _CARD, _LOCKER, _CAT, audit=audit)

    await _memory_text(caps, "Forget all 4242 except the card.")
    await _memory_text(caps, "What is my card?")

    first, second = audit.audits
    assert [row.text for row in first.reached] == [_LOCKER]
    assert [hit.hit.record.text for hit in first.ranking.hits] == [_CARD]
    assert second.reached == ()


async def test_nearest_returns_the_rows_a_search_finds_without_the_policy() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _GYM, _CAT)
    assert caps.memory is not None

    rows = await caps.memory.nearest("Forget everything but my card.", session_id="s", limit=2)

    assert len(rows) == 2
    assert {row.id for row in rows} <= {"m0", "m1", "m2"}


class _EveryCard(_CardOnly):
    def candidate_k(self, k: int) -> int:
        return 4 * k


async def test_the_line_shows_when_one_row_more_holds_the_value_than_the_turn_can_show() -> None:
    store = InMemoryMemoryStore()
    texts = [
        *(f"User: Remember that door {index} opens with 4242." for index in range(5)),
        *(f"User: Remember that card {index} ends in 4242." for index in range(5)),
        "User: Remember that the last door opens with 4242.",
    ]
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        at = _AT + timedelta(minutes=index)
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=at))
    recaller = MemoryRecaller(store, HashEmbedder(), SystemClock(), policy=_EveryCard())

    text = await _memory_text(TurnCapabilities(memory=recaller), "Forget 4242.")

    assert sum(row in text for row in texts) == 2 * FORGET_REACH_LIMIT
    assert texts[-1] not in text
    assert text.endswith(more_held_note("4242"))
