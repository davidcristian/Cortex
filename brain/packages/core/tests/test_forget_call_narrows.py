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
from cortex_core.forget_unnamed import KEPT_ALL
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 21, 8, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "bank": "User: Remember that my bank PIN is 9911.\nAssistant: Noted.",
    "recall": "User: Which number did I ask you to keep?\nAssistant: 4111 1111 1111 4242",
    "noted": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Not a code, noted.",
    "postcode": "User: Remember that my postcode area is north.\nAssistant: Noted.",
    "flat": "User: Remember that my flat is number 7.\nAssistant: Noted.",
}
_THREE = ("locker", "card", "phone")


async def _store(ids: tuple[str, ...], said: str = "") -> InMemoryMemoryStore:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        chat = "chat-new" if name == said else "chat-a"
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id=chat
        )
        await store.add(record)
    return store


def _call(query: str, text: str, call_id: str = "c1") -> ToolCall:
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    return ToolCall(id=call_id, name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)


async def _deleted(
    query: str, text: str, ids: tuple[str, ...] = _THREE, said: str = ""
) -> tuple[set[str], str]:
    store = await _store(ids, said)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call(query, text)
    await tool.card(call)
    result = await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return set(ids) - left, result.content


@pytest.mark.parametrize(
    ("query", "text", "ids"),
    [
        ("Forget my gym code.", "phone", _THREE),
        ("Forget my gym code.", "card", _THREE),
        ("Forget my code.", "phone", _THREE),
        ("Forget that code.", "phone", _THREE),
        ("Forget my code 9999.", "phone", _THREE),
        ("Forget my gym code.", "PIN", ("locker", "bank", "phone")),
        ("Oublie le code de la salle.", "carte", ("casier", "carte")),
        ("Vergiss den Code vom Fitnessstudio.", "Karte", ("spind", "karte")),
    ],
)
async def test_a_word_call_beside_a_code_word_naming_another_stored_row_deletes_nothing(
    query: str, text: str, ids: tuple[str, ...]
) -> None:
    assert await _deleted(query, text, ids) == (set(), f"{KEPT_ALL}.")


@pytest.mark.parametrize(
    ("query", "text", "ids", "gone"),
    [
        ("Forget that.", "phone", _THREE, {"phone"}),
        ("Forget what I just told you.", "phone", _THREE, {"phone"}),
        ("Forget my gym code.", "code", _THREE, {"locker"}),
        ("Forget my gym code.", "locker", _THREE, {"locker"}),
        ("Forget my card code.", "card", _THREE, {"card"}),
        ("Forget my gym code.", "phone", ("card", "phone"), {"phone"}),
        ("Forget my gym code.", "phone", ("phone", "noted"), {"phone"}),
        ("Forget my gym code.", "phone", ("phone", "postcode"), {"phone"}),
        ("Forget everything and my code.", "phone", _THREE, {"phone"}),
        ("Forget my gym password.", "phone", _THREE, {"phone"}),
        ("Forget my card, I got it on 12 March.", "card", _THREE, {"card"}),
        ("Forget what I told you on 12 March.", "phone", _THREE, {"phone"}),
        ("Forget my phone 9999.", "phone", _THREE, {"phone"}),
        ("Forget everything, 9999 too.", "phone", _THREE, {"phone"}),
    ],
)
async def test_a_word_call_beside_no_code_word_naming_a_stored_row_deletes_what_it_names(
    query: str, text: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert (await _deleted(query, text, ids))[0] == gone


async def test_a_later_word_call_keeps_a_row_beside_the_code_row_an_earlier_call_deleted() -> None:
    store = await _store(_THREE)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    for call_id, text in (("c1", "code"), ("c2", "phone")):
        call = _call("Forget my gym code.", text, call_id)
        await tool.card(call)
        await tool.invoke(call)

    assert {hit.record.id for hit in await store.search((1.0, 0.0), k=10)} == {"card", "phone"}


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("my card is 4111", ""),
        ("phone is 0721", ""),
        ("4111 1111 1111 4242", "card"),
    ],
)
async def test_a_call_holding_a_digit_beside_a_message_naming_another_stored_row_deletes_nothing(
    text: str, said: str
) -> None:
    assert (await _deleted("Forget my locker code.", text, said=said))[0] == set()


@pytest.mark.parametrize(
    ("query", "text", "ids", "said", "gone"),
    [
        ("Forget that.", "my card is 4111", _THREE, "", {"card"}),
        ("Forget what I just told you.", "my card is 4111", _THREE, "", {"card"}),
        ("Forget that code.", "4111 1111 1111 4242", _THREE, "card", {"card"}),
        ("Forget my card.", "my card is 4111", _THREE, "", {"card"}),
        ("Forget my locker code and my card.", "my card is 4111", _THREE, "", {"card"}),
        ("Forget my locker code.", "code is 4242", _THREE, "", {"locker"}),
        ("Forget my flat.", "number 7", ("locker", "flat"), "", {"flat"}),
        (
            "Forget my card.",
            "4111 1111 1111 4242",
            ("locker", "card", "recall"),
            "",
            {"card", "recall"},
        ),
        (
            "Forget my locker code and 0721 555 4242.",
            "0721 555 4242",
            _THREE,
            "",
            {"phone"},
        ),
    ],
)
async def test_a_call_holding_a_digit_deletes_a_row_the_message_names_and_its_recall(
    query: str, text: str, ids: tuple[str, ...], said: str, gone: set[str]
) -> None:
    assert (await _deleted(query, text, ids, said))[0] == gone


@pytest.mark.parametrize(
    ("query", "text", "ids", "said"),
    [
        ("Forget my gym code.", "my card is 4111", _THREE, ""),
        ("Forget my gym code.", "phone is 0721", _THREE, ""),
        ("Forget my code.", "my card is 4111", _THREE, ""),
        ("Forget my gym code.", "my card is 4111", _THREE, "phone"),
        ("Oublie le code de la salle.", "ma carte est 4111", ("casier", "carte"), ""),
    ],
)
async def test_a_call_holding_a_digit_beside_a_code_word_naming_another_stored_row_deletes_nothing(
    query: str, text: str, ids: tuple[str, ...], said: str
) -> None:
    assert (await _deleted(query, text, ids, said))[0] == set()


async def test_a_word_call_beside_a_code_word_keeps_the_row_the_chat_just_stored() -> None:
    assert (await _deleted("Forget that code.", "phone", said="phone"))[0] == set()


@pytest.mark.parametrize(
    ("query", "text", "ids", "gone"),
    [
        ("Forget my gym password.", "my card is 4111", _THREE, {"card"}),
        ("Forget my gym code.", "my card is 4111", ("card", "phone"), {"card"}),
        ("Forget my code 4242.", "4242", _THREE, {"locker"}),
        ("Forget every code 4242.", "4242", _THREE, {"locker"}),
        ("Forget everything.", "my card is 4111", _THREE, {"card"}),
        ("Forget everything and my code.", "my card is 4111", _THREE, {"card"}),
    ],
)
async def test_a_call_holding_a_digit_beside_no_code_word_naming_a_stored_row_deletes_what_it_names(
    query: str, text: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert (await _deleted(query, text, ids))[0] == gone


@pytest.mark.parametrize(
    ("query", "text"),
    [
        ("Forget my locker code 4242.", "my card is 4111"),
        ("Forget my gym code 9999.", "my card is 4111"),
        ("Forget my locker code 4242.", "phone is 0721"),
        ("Forget my gym password 9999.", "my card is 4111"),
        ("Forget 9999.", "my card is 4111"),
        ("Forget 9999, not everything.", "my card is 4111"),
    ],
)
async def test_a_call_holding_a_digit_beside_a_message_holding_another_value_deletes_nothing(
    query: str, text: str
) -> None:
    assert (await _deleted(query, text))[0] == set()


@pytest.mark.parametrize(
    ("query", "text", "said"),
    [
        ("Forget 9999.", "phone", ""),
        ("Forget 9999.", "card", ""),
        ("Forget my gym password 9999.", "phone", ""),
        ("Forget the 9999 one.", "phone", ""),
        ("Forget the 9999 one.", "card", "card"),
        ("Forget my phone 9999.", "card", ""),
        ("Oublie 9999.", "carte", ""),
    ],
)
async def test_a_word_call_beside_a_message_holding_a_value_no_row_holds_deletes_nothing(
    query: str, text: str, said: str
) -> None:
    ids = ("locker", "card", "phone", "carte")
    assert (await _deleted(query, text, ids, said))[0] == set()


@pytest.mark.parametrize(
    ("query", "text", "gone"),
    [
        ("Forget 4242.", "4242", {"locker"}),
        ("Forget my locker code 4242.", "locker code is 4242", {"locker"}),
        ("Forget my card 4111.", "my card is 4111", {"card"}),
        ("Forget my locker code 4242 and my card.", "my card is 4111", {"card"}),
        ("Forget my card, I got it on 12 March.", "my card is 4111", {"card"}),
        ("Forget everything, 4242 too.", "my card is 4111", {"card"}),
        ("Forget 0721 555 4242.", "phone is 0721", {"phone"}),
    ],
)
async def test_a_call_holding_a_digit_deletes_a_row_a_message_holding_a_value_also_asks_for(
    query: str, text: str, gone: set[str]
) -> None:
    assert (await _deleted(query, text))[0] == gone


async def test_a_call_holding_the_value_the_chat_just_stored_deletes_it_beside_another_code() -> (
    None
):
    gone = (await _deleted("Forget that code 9999.", "4111 1111 1111 4242", said="card"))[0]
    assert gone == {"card"}
