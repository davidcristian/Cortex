from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    ScoredMemory,
    SystemClock,
    TaintLedger,
    TurnCapabilities,
)
from cortex_core.dispatch_round import ToolLoopContext
from cortex_core.forget_reach import FORGET_REACH_LIMIT, with_forget_reach
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
    store: InMemoryMemoryStore, *texts: str, tainted: Sequence[str] = ()
) -> TurnCapabilities:
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(
            MemoryRecord(
                id=f"m{index}", text=text, embedding=embedding, at=_AT, tainted=text in tainted
            )
        )
    recaller = MemoryRecaller(store, HashEmbedder(), SystemClock(), policy=_CardOnly())
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


async def test_the_rows_already_held_are_returned_as_they_are_on_another_message() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _LOCKER)
    assert caps.memory is not None
    hits = await caps.memory.recall("What is my card?", k=5, session_id="s", turn_id="t")

    assert await with_forget_reach("What is my card?", caps.memory, hits, session_id="s") is hits


async def test_nearest_returns_the_rows_a_search_finds_without_the_policy() -> None:
    caps = await _rig(InMemoryMemoryStore(), _CARD, _GYM, _CAT)
    assert caps.memory is not None

    rows = await caps.memory.nearest("Forget everything but my card.", session_id="s", limit=2)

    assert len(rows) == 2
    assert {row.id for row in rows} <= {"m0", "m1", "m2"}
