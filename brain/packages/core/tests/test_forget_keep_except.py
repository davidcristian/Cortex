from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.forget_unnamed import KEPT_LINE, keep_words, unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 11, 5, 0, 0, tzinfo=UTC)


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
        session_id=None,
    )


_CARD = _record("card", "User: My card is 4111 1111 1111 4242.\nAssistant: Noted.")
_CODE = _record("code", "User: Code 4242.\nAssistant: Noted.", 1)
_BIKE = _record("bike", "User: Remember that my bike lock code is 7319.\nAssistant: Noted.")
_SHED = _record(
    "shed", "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted.", 1
)


def _kept(text: str, query: str, *rows: MemoryRecord) -> list[str]:
    return [record.id for record in unnamed(rows, text, query)]


@pytest.mark.parametrize(
    "query",
    [
        "Forget the code 4242 except the card.",
        "Forget the code 4242, excluding the card.",
        "Forget the code 4242 but not my card.",
        "Forget the code 4242, keep the card.",
    ],
)
def test_an_except_clause_beside_a_code_word_and_a_value_lists_the_row_holding_it_whole(
    query: str,
) -> None:
    assert _kept("4242", query, _CARD, _CODE) == ["card"]


def test_an_except_clause_beside_no_word_and_no_value_lists_no_row() -> None:
    assert _kept("4242", "Forget everything except my card.", _CARD, _CODE) == ["card", "code"]


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319 except the shed one.",
        "Forget my bike lock code 7319, excluding the shed one.",
        "Oublie le code du bike lock 7319, sauf celui du shed.",
        "Oublie le code du bike lock 7319 hormis celui du shed.",
        "Oublie le code du bike lock 7319, excepté celui du shed.",
        "Vergiss den bike lock Code 7319 außer den shed Code.",
        "Vergiss den bike lock Code 7319, ausgenommen den shed Code.",
        "Olvida el código del bike lock 7319 excepto el del shed.",
        "Olvida el código del bike lock 7319, salvo el del shed.",
        "Uită codul de la bike lock 7319, exceptând cel de la shed.",
    ],
)
def test_a_fact_named_only_after_an_except_word_is_kept(query: str) -> None:
    assert _kept("7319", query, _BIKE, _SHED) == ["shed"]


_NAMED = _record("named", "User: The exception code, also the excepted one, is 4242.", 1)


@pytest.mark.parametrize(
    ("query", "row", "kept"),
    [
        ("Forget the code 4242.", _CARD, []),
        ("Forget the exception code 4242.", _NAMED, ["code"]),
        ("Forget the excepted code 4242.", _NAMED, ["code"]),
    ],
)
def test_a_word_only_like_except_opens_no_keep_clause(
    query: str, row: MemoryRecord, kept: list[str]
) -> None:
    assert (_kept("4242", query, _CODE, row), keep_words(query)) == (kept, set())


@pytest.mark.parametrize(
    "query",
    [
        "Oublie le code 4242 moins celui de la carte.",
        "Olvida el código 4242 menos el de la tarjeta.",
        "Uită codul 4242 mai puțin cel de pe card.",
    ],
)
def test_a_word_that_can_mean_minus_opens_no_keep_clause(query: str) -> None:
    assert keep_words(query) == set()


async def test_a_card_lists_the_row_before_except_and_keeps_the_row_after_it() -> None:
    store = InMemoryMemoryStore()
    bike = _record("bike", "User: My bike code is 4242.\nAssistant: Noted.", 2)
    for record in (_CARD, _CODE, bike):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(turn_id="t1", query="Forget my bike code 4242 except the card.")
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    assert card is not None
    lines = card.splitlines()
    assert (len(lines), lines[2]) == (5, KEPT_LINE)
    assert ("bike code" in lines[1], "My card" in lines[3]) == (True, True)
    await tool.invoke(call)
    hits = await store.search((1.0, 0.0), k=10)
    assert sorted(hit.record.id for hit in hits) == ["card", "code"]


@pytest.mark.parametrize("word", ["except", "excluding", "sauf", "außer", "excepto"])
def test_an_except_word_names_no_fact_to_keep(word: str) -> None:
    assert keep_words(f"Forget my bike lock code 7319 {word} the shed one.") == {"shed"}


@pytest.mark.parametrize(
    "query",
    ["Forget everything but my card.", "Forget all but my card.", "Forget them all but my card."],
)
def test_but_after_a_word_for_all_keeps_the_row_it_names(query: str) -> None:
    assert (_kept("4242", query, _CARD, _CODE), keep_words(query)) == (["card", "code"], {"card"})


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my card 4242, but quickly.", ["code"]),
        ("Forget all of my card 4242, but quickly.", ["code"]),
        ("Forget everything, but my card first.", ["code"]),
        ("Forget all my card numbers but quickly.", ["code"]),
        ("Forget it but quickly.", ["code"]),
        ("Forget it, but quickly and all.", ["code"]),
        ("Forget 4242 but do it now.", []),
    ],
)
def test_a_but_after_no_word_for_all_opens_no_keep_clause(query: str, kept: list[str]) -> None:
    assert (_kept("4242", query, _CARD, _CODE), keep_words(query)) == (kept, set())


def test_a_keep_verb_after_but_still_lists_the_row_before_it() -> None:
    query = "Forget my card, but keep it short."
    assert (_kept("4242", query, _CARD, _CODE), keep_words(query)) == (["code"], {"short"})


async def test_a_forget_of_everything_but_the_card_deletes_no_row() -> None:
    store = InMemoryMemoryStore()
    for record in (_CARD, _CODE):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(turn_id="t1", query="Forget everything but my card.")
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    await tool.invoke(call)
    hits = await store.search((1.0, 0.0), k=10)
    assert (card, sorted(hit.record.id for hit in hits)) == (None, ["card", "code"])
