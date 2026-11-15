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
from cortex_core.forget_unnamed import KEPT_ALL, unnamed
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 7, 0, 0, tzinfo=UTC)
_ROWS = {
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "visa": "User: Remember that my Visa is 4000 1234 5678 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
}
_TWO = ("card", "gym")
_THREE = ("locker", "card", "phone")


async def _forget(query: str, text: str, *ids: str) -> tuple[str, list[str]]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    result = await tool.invoke(call)
    return result.content, sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "text", "ids", "left"),
    [
        ("Forget everything but my card.", "gym code", _TWO, ["card"]),
        ("Forget everything but my card.", "gym", _TWO, ["card"]),
        ("Forget everything but my card.", "gym code is 4242", _TWO, ["card"]),
        ("Forget everything but my card.", "4242", _TWO, ["card"]),
        ("Forget everything except my card.", "gym code", _TWO, ["card"]),
        ("Forget all but my card.", "gym code", _TWO, ["card"]),
        ("Forget everything. Keep my card.", "gym code", _TWO, ["card"]),
        ("Forget everything, not the card.", "gym code", _TWO, ["card"]),
        (
            "Forget everything except the card and the phone.",
            "locker code",
            _THREE,
            ["card", "phone"],
        ),
        ("Forget everything but my card.", "locker code", _THREE, ["card", "phone"]),
        ("Forget everything but my card.", "phone", _THREE, ["card", "locker"]),
        ("Oublie tout sauf ma carte.", "casier", ("casier", "carte"), ["carte"]),
        ("Vergiss alle außer der Karte.", "Handy", ("spind", "karte", "handy"), ["karte", "spind"]),
        ("Forget all 4242 except the card.", "locker code", _THREE, ["card", "phone"]),
        ("Forget all 4242 except the card.", "phone", _THREE, ["card", "locker"]),
        ("Forget all 4242 except the card.", "0721 555 4242", _THREE, ["card", "locker"]),
        ("Forget all 4242 except the card.", "4242", _THREE, ["card"]),
        ("Forget 4242 except the card.", "locker code", _THREE, ["card", "phone"]),
    ],
)
async def test_a_call_naming_a_row_the_keep_clause_does_not_name_deletes_it(
    query: str, text: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert (await _forget(query, text, *ids))[1] == left


@pytest.mark.parametrize(
    ("query", "text", "ids"),
    [
        ("Forget everything but my card.", "card", _TWO),
        ("Forget everything but my card.", "4111 1111 1111 4242", _TWO),
        ("Forget all 4242 except the card.", "card", _THREE),
        ("Forget everything but my Visa.", "gym code", _TWO),
        ("Forget everything but my card and my Visa.", "gym code", _TWO),
        ("Forget everything but my passport.", "gym code", _TWO),
        ("Forget everything but my car.", "gym code", _TWO),
        ("Forget all 4242 except the Visa.", "locker code", _THREE),
        ("Forget them all but my card.", "gym code", _TWO),
        ("I forgot everything but my card.", "gym code", _TWO),
        ("We forget everything but my card.", "gym code", _TWO),
        ("Forget everything but everything on my card.", "gym code", _TWO),
        ("Forget everything except the card, just the phone.", "locker code", _THREE),
        ("Forget everything except the card, the phone too.", "locker code", _THREE),
        ("Forget everything except the card only on the phone.", "locker code", _THREE),
        ("Forgot everything but my card.", "gym code", _TWO),
        ("Now all but my card.", "gym code", _TWO),
        ("Supprime tout sauf ma carte.", "casier", ("casier", "carte")),
        ("Vergiss alle, die Karte bleibt.", "gym code", _TWO),
        ("Vergiss alle außer der Karte, nur die Karte.", "Handy", ("spind", "karte", "handy")),
        ("Uită 4242 dar nu cardul doar de pe card.", "dulap", ("dulap", "cardul")),
        ("Forget it except the card.", "gym code", _TWO),
        ("Forget my locker code but keep the card.", "phone", _THREE),
        ("Forget the locker code, not the card.", "phone", _THREE),
        ("Keep my card.", "gym code", _TWO),
    ],
)
async def test_a_call_naming_a_row_the_message_does_not_ask_for_keeps_every_row(
    query: str, text: str, ids: tuple[str, ...]
) -> None:
    content, left = await _forget(query, text, *ids)
    assert (content, left) == (f"{KEPT_ALL}.", sorted(ids))


async def test_a_keep_clause_naming_one_of_two_card_rows_by_another_word_keeps_the_visa() -> None:
    assert (await _forget("Forget everything but my Visa.", "4242", "visa", "gym"))[1] == ["visa"]


def test_a_word_naming_a_stored_row_outside_the_matches_reads_the_keep_clause() -> None:
    gym = MemoryRecord(id="gym", text=_ROWS["gym"], embedding=(1.0, 0.0), at=_AT, session_id=None)
    query = "Forget everything but my card."
    kept = [
        [row.id for row in unnamed([gym], "gym code", query, read=read)]
        for read in (frozenset[str](), frozenset({"card"}), frozenset({"visa"}))
    ]
    assert kept == [["gym"], [], ["gym"]]
