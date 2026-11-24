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
from cortex_core.forget_clauses import after_kept
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 24, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
}
_ENGLISH = ("card", "phone", "locker")
_FRENCH = ("carte", "telephone", "casier")
_GERMAN = ("karte", "handy", "spind")
_ROMANIAN = ("cardul", "dulap", "telefonul")


async def _left(query: str, ids: tuple[str, ...], text: str = "4242") -> list[str]:
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
    await tool.invoke(call)
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))


@pytest.mark.parametrize(
    ("query", "ids", "kept"),
    [
        ("Forget 4242, the card, the phone stays, the locker too.", _ENGLISH, {"phone", "locker"}),
        ("Forget all 4242, the card. The phone stays, the locker too.", _ENGLISH, {"locker"}),
        ("Forget 4242, the card but the phone, the locker too.", _ENGLISH, {"phone", "locker"}),
        ("Forget 4242, the card but the phone, also the locker.", _ENGLISH, {"locker"}),
        ("Forget 4242, the card but the phone, the locker as well.", _ENGLISH, {"locker"}),
        ("Forget the card but not the phone, and the locker too.", _ENGLISH, {"phone", "locker"}),
        (
            "Forget 4242, the card, the phone stays, the gym, the locker.",
            (*_ENGLISH, "gym"),
            {"gym", "locker"},
        ),
        (
            "Oublie 4242, la carte, le téléphone reste, le casier aussi.",
            _FRENCH,
            {"telephone", "casier"},
        ),
        ("Vergiss 4242, die Karte, das Handy bleibt, den Spind auch.", _GERMAN, {"handy", "spind"}),
        ("Uită 4242, cardul, dulapul rămâne, și telefonul.", _ROMANIAN, {"dulap", "telefonul"}),
        (
            "Forget the card 4242 but the phone, the locker too, keep the phone.",
            _ENGLISH,
            {"phone", "locker"},
        ),
        (
            "Forget 4242, the card, the phone stays, the locker too. The phone stays.",
            _ENGLISH,
            {"phone", "locker"},
        ),
        (
            "Oublie tous les 4242, la carte, le téléphone reste, le casier aussi, "
            "garde le téléphone.",
            _FRENCH,
            {"telephone", "casier"},
        ),
        (
            "Uită toate 4242, dulapul, cardul rămâne, și telefonul, cardul rămâne.",
            _ROMANIAN,
            {"cardul", "telefonul"},
        ),
    ],
)
async def test_an_item_after_a_clause_any_reading_keeps_is_kept(
    query: str, ids: tuple[str, ...], kept: set[str]
) -> None:
    assert kept <= set(await _left(query, ids))


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Keep the phone, forget the card, the locker too.", _ENGLISH, ["phone"]),
        ("Forget the card 4242, the phone stays. Forget the locker 4242 too.", _ENGLISH, ["phone"]),
        ("Forget the card 4242, the phone stays, forget the locker 4242 too.", _ENGLISH, ["phone"]),
        ("Forget the card 4242, the phone 4242, the locker too.", _ENGLISH, []),
    ],
)
async def test_an_item_after_a_forget_verb_or_no_kept_clause_is_deleted(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    assert await _left(query, ids) == left


@pytest.mark.parametrize(
    ("query", "kept", "words"),
    [
        ("Forget 4242, the phone stays, the locker too.", {"phone"}, ["the", "locker", "too"]),
        ("Forget the phone, the locker too.", {"phone"}, ["the", "locker", "too"]),
        ("The phone stays, forget the card, the locker too.", {"phone"}, []),
        ("Forget 4242, the phone stays, forget the locker, the gym.", {"phone"}, []),
        ("The phone stays, the locker too, forget 4242.", {"phone"}, ["the", "locker", "too"]),
        ("Forget 4242, the card, the locker too.", {"phone"}, []),
        (
            "Forget the card 4242, the phone too, keep the card.",
            {"card"},
            ["the", "phone", "too", "keep", "the", "card"],
        ),
        ("The phone stays but forget the card, the locker too.", {"phone"}, []),
        ("Forget all 4242 but the phone, the locker too.", {"phone"}, ["the", "locker", "too"]),
    ],
)
def test_after_kept_reads_the_clauses_with_no_forget_verb_after_a_kept_word(
    query: str, kept: set[str], words: list[str]
) -> None:
    assert after_kept(query, frozenset(kept)) == words
