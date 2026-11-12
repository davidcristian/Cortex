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
from cortex_core.forget_results import forgot
from cortex_core.forget_unnamed import KEPT_ALL, KEPT_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 9, 1, 0, 0, tzinfo=UTC)
_GYM = "User: Remember that my gym locker number is 5521.\nAssistant: I've noted that."
_SHED = "User: Remember that the shed padlock code is also 5521.\nAssistant: Noted."
_ASKED = "Forget my gym locker number."


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
    )


async def _forget(
    text: str, query: str, *rows: tuple[str, str]
) -> tuple[str | None, str, bool | None, list[str]]:
    store = InMemoryMemoryStore()
    for minutes, (record_id, row) in enumerate(rows):
        await store.add(_record(record_id, row, minutes))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return card, result.content, result.numbers_left, left


async def test_a_value_first_forget_keeps_the_fact_the_message_does_not_name() -> None:
    card, said, numbers_left, left = await _forget("5521", _ASKED, ("gym", _GYM), ("shed", _SHED))
    assert card is not None
    lines = card.splitlines()
    assert lines[0] == "Deletes for good, with no undo, these 1 remembered exchanges:"
    assert lines[2] == KEPT_LINE
    assert "gym locker" in lines[1]
    assert "shed padlock" in lines[3]
    assert said == f"{forgot(1, 1, 1)}."
    assert "forget of" not in said
    assert numbers_left is True
    assert left == ["shed"]


async def test_a_value_reaching_only_unnamed_facts_shows_no_card_and_keeps_them() -> None:
    card, said, numbers_left, left = await _forget("5521", "Forget my bike code.", ("shed", _SHED))
    assert (card, said, numbers_left, left) == (None, f"{KEPT_ALL}.", None, ["shed"])


@pytest.mark.parametrize(
    "query", ["Forget 5521.", "Forget that one, 5521.", "", "Oublie le 5521 partout."]
)
async def test_a_message_naming_the_value_and_no_fact_deletes_every_row(query: str) -> None:
    _, _, _, left = await _forget("5521", query, ("gym", _GYM), ("shed", _SHED))
    assert left == []


@pytest.mark.parametrize("query", ["Forget it.", "Forget that number."])
async def test_a_message_naming_no_word_keeps_the_rows_other_chats_stored(query: str) -> None:
    card, said, _, left = await _forget("5521", query, ("gym", _GYM), ("shed", _SHED))
    assert (card, said, left) == (None, f"{KEPT_ALL}.", ["gym", "shed"])


async def test_a_label_text_is_not_read_against_the_message() -> None:
    _, _, _, left = await _forget("padlock", _ASKED, ("gym", _GYM), ("shed", _SHED))
    assert left == ["gym"]


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget that the gym number is mine.", ["shed"]),
        ("Forget my gym code.", ["shed"]),
        ("Please forget the code of my shed.", ["gym"]),
        ("Forget my gym and shed numbers.", []),
    ],
)
async def test_common_and_code_words_name_no_fact(query: str, kept: list[str]) -> None:
    _, _, _, left = await _forget("5521", query, ("gym", _GYM), ("shed", _SHED))
    assert left == kept


async def test_a_recall_holding_the_value_only_in_its_reply_is_deleted() -> None:
    recall = "User: Which number did I ask you to keep? Reply with only it.\nAssistant: 5521"
    _, _, _, left = await _forget("5521", _ASKED, ("gym", _GYM), ("recall", recall))
    assert left == []


async def test_a_row_with_no_reply_is_read_whole_and_kept_when_unnamed() -> None:
    bare = "the shed padlock code is 5521"
    _, said, _, left = await _forget("5521", _ASKED, ("gym", _GYM), ("bare", bare))
    assert left == ["bare"]
    assert said == f"{forgot(1, 1, 1)}."


@pytest.mark.parametrize(
    ("text", "query", "rows"),
    [
        (
            "7731",
            "Oublie le code de mon casier à la piscine.",
            [
                "User: Souviens-toi que le code de mon casier à la piscine est 7731.\n"
                "Assistant: C'est noté.",
                "User: Which number did I give you for the pool locker? Reply with only the "
                "number.\nAssistant: 7731",
                "User: Quel est le code de mon casier à la piscine ?\nAssistant: 7731.",
                "User: What is my swimming pool locker code?\nAssistant: Your swimming pool "
                "locker code is 7731.",
            ],
        ),
        (
            "1987",
            "Forget my door code.",
            [
                "User: Remember that my door code is 1987.\nAssistant: Noted.",
                "User: What number opens my front door?\nAssistant: 1987 opens it.",
                "User: Which number did I give you for the front door? Reply with only the "
                "number.\nAssistant: 1987",
            ],
        ),
        (
            "5819",
            "Forget the code of my gym locker.",
            [
                "User: Remember that my gym locker code is 5819.\nAssistant: Noted.",
                'User: In one sentence that starts with "The code for", what opens my gym '
                "locker?\nAssistant: The code for your gym locker is 5819.",
            ],
        ),
        (
            "0612345678",
            "Forget my phone number and my passport number.",
            ["User: Remember that my phone number is 0612345678.\nAssistant: Noted."],
        ),
    ],
)
async def test_each_recorded_value_first_draw_still_deletes_every_row(
    text: str, query: str, rows: list[str]
) -> None:
    named = [(f"r{index}", row) for index, row in enumerate(rows)]
    _, said, _, left = await _forget(text, query, *named)
    assert left == []
    assert said == f"{forgot(len(rows), 0, 0)}."


_LABELLED = "Forget my gym locker number, it is 5521."


@pytest.mark.parametrize(
    "query",
    [
        _LABELLED,
        "Forget my gym locker number. It is 5521.",
        "Forget 5521, the gym one.",
        "Forget my gym locker number 5521 that I gave you.",
    ],
)
async def test_a_message_naming_the_value_beside_a_label_keeps_the_fact_it_does_not_name(
    query: str,
) -> None:
    card, said, numbers_left, left = await _forget("5521", query, ("gym", _GYM), ("shed", _SHED))
    assert card is not None
    lines = card.splitlines()
    assert (len(lines), lines[2]) == (4, KEPT_LINE)
    assert "gym locker" in lines[1]
    assert "shed padlock" in lines[3]
    assert (said, numbers_left, left) == (f"{forgot(1, 1, 1)}.", True, ["shed"])


@pytest.mark.parametrize(
    "query",
    [
        "Forget 5521.",
        "Forget 5521 everywhere.",
        "Forget all of 5521.",
        "Forget 5521 from your records.",
        "Forget my gym locker number and 5521 everywhere.",
        "Forget my gym locker number, it is 5521, and every other 5521 too.",
        "Forget my gym locker and shed padlock numbers, both are 5521.",
        "Forget my bike code, it is 5521.",
        "Vergiss die Nummer 5521 überall.",
        "Oublie le code du casier de la gym, c'est 5521, partout.",
    ],
)
async def test_a_message_naming_the_value_and_no_fact_apart_deletes_every_row(query: str) -> None:
    _, said, _, left = await _forget("5521", query, ("gym", _GYM), ("shed", _SHED))
    assert (said, left) == (f"{forgot(2, 0, 0)}.", [])


async def test_recalls_restating_the_labelled_value_are_deleted_and_the_other_fact_kept() -> None:
    reply_only = "User: Which number did I ask you to keep? Reply with only it.\nAssistant: 5521"
    asked = "User: What is 5521 for?\nAssistant: It opens your gym locker."
    rows = [("gym", _GYM), ("recall", reply_only), ("asked", asked), ("shed", _SHED)]
    _, said, _, left = await _forget("5521", _LABELLED, *rows)
    assert (said, left) == (f"{forgot(3, 1, 1)}.", ["shed"])


async def _two_calls(rows: list[tuple[str, str]], turns: tuple[str, str]) -> tuple[str, list[str]]:
    store = InMemoryMemoryStore()
    for minutes, (record_id, row) in enumerate(rows):
        await store.add(_record(record_id, row, minutes))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    content = ""
    for index, (text, turn) in enumerate(zip(("gym locker number", "5521"), turns, strict=True)):
        stamp = TurnStamp(session_id="chat-a", turn_id=turn, query=_LABELLED)
        call = ToolCall(
            id=f"c{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp
        )
        await tool.card(call)
        content = (await tool.invoke(call)).content
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return content, left


async def test_a_later_value_call_keeps_the_fact_once_the_labelled_one_was_deleted() -> None:
    said, left = await _two_calls([("gym", _GYM), ("shed", _SHED)], ("t1", "t1"))
    assert (said, left) == (f"{KEPT_ALL}.", ["shed"])


async def test_a_row_deleted_in_another_turn_names_no_fact_for_this_one() -> None:
    said, left = await _two_calls([("gym", _GYM), ("shed", _SHED)], ("t1", "t2"))
    assert (said, left) == (f"{forgot(1, 0, 0)}.", [])


async def test_a_row_asked_to_keep_beside_an_inside_row_gets_the_kept_result() -> None:
    pin = "User: My PIN is 55210.\nAssistant: Noted."
    query = "Forget my gym locker number but keep the shed padlock code."
    rows = (("gym", _GYM), ("shed", _SHED), ("pin", pin))
    _, said, numbers_left, left = await _forget("5521", query, *rows)
    assert said == f"{forgot(1, 0, 1)}."
    assert "asks to keep them" in said
    assert (numbers_left, left) == (False, ["pin", "shed"])
