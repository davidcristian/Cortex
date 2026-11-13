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
from cortex_core.forget_unnamed import KEPT_LINE, unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 9, 5, 0, 0, tzinfo=UTC)
_BIKE = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
_SHED_RECALL = "User: What is the shed padlock code?\nAssistant: It is 7319."


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
        session_id=None,
    )


_TWO = (_record("bike", _BIKE), _record("shed", _SHED, 1))


def _kept(query: str, *rows: MemoryRecord) -> list[str]:
    return [record.id for record in unnamed(rows or _TWO, "7319", query)]


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319, keep the shed padlock one.",
        "Forget my bike lock code 7319 but not the shed one.",
        "Forget my bike lock code, not the shed one.",
        "Forget my bike lock code 7319 and not the shed one.",
        "Keep the shed padlock code and forget the bike lock code 7319.",
        "Can you keep the shed one and forget my bike lock code 7319?",
        "Forget my bike lock code 7319, but don't forget the shed one.",
        "Forget my bike lock code 7319, it is not the shed one.",
        "Forget my bike lock code 7319, it's not the shed one.",
        "Oublie le code du bike lock 7319, mais pas celui du shed.",
        "Vergiss den bike lock Code 7319, aber nicht den shed Code.",
        "Olvida el código del bike lock 7319, pero no el del shed.",
        "Uită codul de la bike lock 7319, dar nu pe cel de la shed.",
    ],
)
def test_a_fact_named_only_in_a_clause_asking_to_keep_is_kept(query: str) -> None:
    assert _kept(query) == ["shed"]


@pytest.mark.parametrize(
    "query",
    [
        "Forget 7319, keep the shed one.",
        "Forget 7319 everywhere, but keep the shed one.",
        "Vergiss 7319, behalte den shed Code.",
        "Uită 7319, păstrează codul de la shed.",
    ],
)
def test_a_keep_clause_beside_a_value_naming_no_fact_lists_the_rows_holding_it_whole(
    query: str,
) -> None:
    assert _kept(query) == ["shed"]


@pytest.mark.parametrize(
    "query",
    ["Oublie 7319, garde celui du shed.", "Forget 7319, keep the shed one and the boat one."],
)
def test_a_keep_clause_with_a_word_naming_no_row_beside_a_value_keeps_every_row(
    query: str,
) -> None:
    assert _kept(query) == ["bike", "shed"]


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my bike lock code 7319, keep everything else.", ["shed"]),
        ("Forget the not so new shed padlock code 7319.", ["bike"]),
        ("Don't keep my bike lock code 7319.", ["shed"]),
        ("Do not keep the shed padlock code 7319.", ["bike"]),
        ("Forget my bike lock code 7319, don't keep the shed one either.", []),
        ("Ne garde pas le code du shed 7319.", ["bike"]),
        ("I keep forgetting it, forget my bike lock code 7319.", ["shed"]),
        ("Forget 7319.", []),
    ],
)
def test_a_negation_or_keep_verb_that_asks_for_no_keep_leaves_the_words_to_forget(
    query: str, kept: list[str]
) -> None:
    assert _kept(query) == kept


def test_a_word_also_named_outside_the_keep_clause_names_a_fact_to_forget() -> None:
    lock = _record("shed", "User: Remember that the shed lock code is 7319.\nAssistant: Noted.", 1)
    assert _kept("Forget my bike lock code 7319, keep the shed lock code.", _TWO[0], lock) == [
        "shed"
    ]
    assert _kept("Keep the bike one, forget the bike lock code 7319.") == ["shed"]


def test_a_row_named_by_a_keep_clause_and_by_a_word_to_forget_is_kept() -> None:
    lock = _record("shed", "User: Remember that the shed lock code is 7319.\nAssistant: Noted.", 1)
    assert _kept("Forget my lock codes 7319, keep the shed one.", _TWO[0], lock) == ["shed"]
    both = _record("both", "User: The bike shed code is 7319.\nAssistant: Noted.", 2)
    assert _kept("Forget the bike code 7319, keep the shed one.", _TWO[0], both) == ["both"]


def test_a_keep_clause_keeps_a_row_holding_the_value_only_in_its_reply() -> None:
    recall = _record("recall", _SHED_RECALL, 2)
    assert _kept("Forget the bike code 7319, keep the shed one.", _TWO[0], recall) == ["recall"]
    assert _kept("Forget 7319.", _TWO[0], recall) == []


def test_a_keep_verb_alone_names_no_fact() -> None:
    keeper = _record("keeper", "User: Keep the gate code 7319 handy.\nAssistant: Noted.", 2)
    assert _kept("Forget my bike lock code 7319, keep it.", _TWO[0], keeper) == ["keeper"]
    assert _kept("Forget 7319, keep it.", _TWO[0], keeper) == ["bike", "keeper"]


@pytest.mark.parametrize(
    ("query", "row"),
    [
        ("Forget my do not disturb PIN 7319.", "the do not disturb PIN is 7319"),
        ("Forget 7319, the do not disturb PIN.", "the do not disturb PIN is 7319"),
        ("Forget the don't disturb PIN 7319.", "the don't disturb PIN is 7319"),
        ("Forget the guardian PIN 7319.", "the guardian PIN is 7319"),
        ("Forget the keepsake box PIN 7319.", "the keepsake box PIN is 7319"),
        ("Forget the conservatory alarm 7319.", "the conservatory alarm is 7319"),
        ("Olvida el pin de mantenimiento del ascensor 7319.", "el pin del ascensor es 7319"),
    ],
)
def test_a_negation_or_keep_word_inside_the_asked_facts_name_names_it(query: str, row: str) -> None:
    asked = _record("asked", f"User: Remember that {row}.\nAssistant: Noted.", 1)
    assert _kept(query, _TWO[0], asked) == ["bike"]


@pytest.mark.parametrize(
    "query",
    [
        "Forget my bike lock code 7319, but do not forget the shed one.",
        "Forget my bike lock code 7319, and keeping the shed one.",
        "Olvida el código del bike lock 7319, guarda el del shed.",
        "Olvida el código del bike lock 7319, mantenlo el del shed.",
        "Oublie le code du bike lock 7319, conserve celui du shed.",
    ],
)
def test_a_keep_verb_form_or_a_lead_after_no_naming_word_still_asks_to_keep(query: str) -> None:
    assert _kept(query) == ["shed"]


_LOCK = "User: Remember that the shed lock code is also 7319.\nAssistant: Noted."


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my bike lock code, keep the shed one.", ["shed"]),
        ("Oublie le code du bike lock, garde celui du shed.", ["shed"]),
        ("Forget my bike lock code.", []),
        ("Forget my bike lock code, keep it.", []),
        ("Forget my bike lock code, don't keep the shed one either.", []),
    ],
)
def test_a_keep_clause_keeps_its_row_when_the_call_text_holds_no_value(
    query: str, kept: list[str]
) -> None:
    rows = (_record("bike", _BIKE), _record("shed", _LOCK, 1))
    assert [record.id for record in unnamed(rows, "bike lock code", query)] == kept


async def test_a_card_for_words_lists_no_row_its_keep_clause_names() -> None:
    store = InMemoryMemoryStore()
    for record in (_record("bike", _BIKE), _record("shed", _LOCK, 1)):
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(turn_id="t1", query="Forget my bike lock code, keep the shed one.")
    call = ToolCall(
        id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "bike lock code"}, stamp=stamp
    )
    card = await tool.card(call)
    assert card is not None
    lines = card.splitlines()
    assert (len(lines), lines[2]) == (4, KEPT_LINE)
    assert ("bike lock" in lines[1], "shed lock" in lines[3]) == (True, True)
    await tool.invoke(call)
    assert [hit.record.id for hit in await store.search((1.0, 0.0), k=10)] == ["shed"]
