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
from cortex_core.forget_clauses import (
    ADDITION,
    UNREAD,
    before_value,
    beside,
    forget_end,
    kept_again,
)
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 24, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "car": "User: Remember that my car is parked in bay 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
}


async def _left(query: str, kept: str, text: str = "4242") -> list[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(("car", "phone", "locker", kept)):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "kept"),
    [
        ("Forget my cart, the phone stays.", "phone"),
        ("Forget my cart 4242, the phone stays.", "phone"),
        ("Forget my cart 1234, the phone stays.", "phone"),
        ("Forget my cart, the car stays.", "car"),
        ("Oublie mon cart, le casier reste.", "casier"),
        ("Oublie mon cart 4242, le casier reste.", "casier"),
        ("Olvida mi cart, el gimnasio se queda.", "gimnasio"),
        ("Olvida mi cart 4242, el gimnasio se queda.", "gimnasio"),
        ("Uită cart, dulap rămâne.", "dulap"),
        ("Uită cart 4242, dulap rămâne.", "dulap"),
    ],
)
async def test_a_row_a_later_clause_names_is_kept_with_or_without_the_value(
    query: str, kept: str
) -> None:
    assert kept in await _left(query, kept)


@pytest.mark.parametrize(
    ("query", "kept", "text"),
    [
        ("Forget my phones 1234, the phone stays.", "phone", "phone"),
        ("Forget my phones 1234, the phone stays.", "phone", "4242"),
        ("Forget my lockers 1234, the locker stays.", "locker", "locker"),
        ("Forget my lockers 1234, the locker stays.", "locker", "4242"),
        ("Forget my remembered 1234, the locker stays.", "locker", "locker"),
        ("Forget my remembered 1234, the locker stays.", "locker", "4242"),
    ],
)
async def test_a_call_text_naming_a_row_only_in_a_later_clause_keeps_that_row(
    query: str, kept: str, text: str
) -> None:
    assert kept in await _left(query, kept, text)


@pytest.mark.parametrize(
    ("query", "text"),
    [
        ("Forget my phone, the locker stays.", "phone"),
        ("Forget the locker. Forget the phone.", "phone"),
        ("Forget the locker, the phone too.", "phone"),
        ("Forget the locker, also the phone.", "phone"),
    ],
)
async def test_a_call_text_naming_a_row_the_message_asks_to_delete_deletes_it(
    query: str, text: str
) -> None:
    assert "phone" not in await _left(query, "locker", text)


@pytest.mark.parametrize(
    ("query", "text", "left"),
    [
        ("Forget 4242, the car, but not the locker.", "car", ["locker", "locker", "phone"]),
        ("Forget it 4242, the phone 4242, the locker stays.", "phone", ["car", "locker", "locker"]),
        ("Forget 4242, the car, except the locker.", "car", ["locker", "locker", "phone"]),
        (
            "Forget the car 4242, the phone and the locker too.",
            "phone",
            ["car", "locker", "locker"],
        ),
    ],
)
async def test_a_call_text_naming_a_row_after_the_first_forget_clause_deletes_that_row(
    query: str, text: str, left: list[str]
) -> None:
    assert await _left(query, "locker", text) == left


@pytest.mark.parametrize(
    ("query", "text"),
    [
        ("Forget 4242, the phone, the locker stays.", "phone"),
        ("Forget 4242, the car, the locker stays.", "car"),
        ("Forget 4242, the car, the phone, the locker stays.", "4242"),
        ("Forget all 4242, the car, the phone, the locker stays too.", "car"),
        ("Forget 4242, the car, also the phone, the locker stays.", "4242"),
        ("Forget 4242, the car, the phone, the locker I keep.", "4242"),
    ],
)
async def test_a_row_named_in_a_list_before_a_stays_clause_is_kept(query: str, text: str) -> None:
    assert await _left(query, "locker", text) == ["car", "locker", "locker", "phone"]


@pytest.mark.parametrize(
    "query",
    [
        "Forget 4242 on the car, the locker stays.",
        "Forget 4242, only the car, the locker stays.",
        "Forget 4242 the car, the locker stays.",
        "Forget 4242, the car 4242, the locker stays.",
        "Forget 4242, the car, keep the locker.",
    ],
)
async def test_a_row_named_beside_the_value_before_a_stays_clause_is_deleted(query: str) -> None:
    assert await _left(query, "locker") == ["locker", "locker", "phone"]


@pytest.mark.parametrize(
    ("query", "gone"),
    [
        ("Forget my car, the phone stays.", {"car"}),
        ("Forget my car, the phone too.", {"car", "phone"}),
        ("Forget my car, also the phone.", {"car", "phone"}),
        ("Forget my car. Forget the phone.", {"car", "phone"}),
        ("The phone stays, forget my car.", {"car"}),
    ],
)
async def test_a_row_the_message_asks_to_delete_without_the_value_is_deleted(
    query: str, gone: set[str]
) -> None:
    assert gone.isdisjoint(await _left(query, "locker"))


def test_a_message_lacking_the_value_reads_the_end_of_a_forget_clause_as_its_place() -> None:
    assert forget_end(["forget", "my", "cart"]) == 3
    assert forget_end(["the", "phone", "stays"]) is None
    assert before_value("Forget my cart, the phone stays.", "4242") == ["forget", "my", "cart"]
    assert before_value("The phone stays.", "4242") == []
    named, none = frozenset({"phone"}), frozenset[str]()
    assert beside("Forget my cart, the phone stays.", "4242", named, none)[UNREAD] == {"phone"}
    assert beside("Forget my cart, the phone too.", "4242", named, none)[ADDITION] == {"phone"}
    assert not any(beside("The phone stays.", "4242", named, none).values())


def test_a_call_text_naming_a_row_in_a_message_with_no_forget_verb_is_read_where_it_is() -> None:
    named = frozenset({"card", "phone", "locker"})
    assert kept_again("The card, the phone, the locker stays.", "phone", named) == {"locker"}
