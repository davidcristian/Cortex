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
from cortex_core import forget_forms as forms
from cortex_core.forget_unnamed import quantifies
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 9, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym code is 7391.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "telefono": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
    "fahrrad": "User: Merke dir, mein Fahrradcode ist 4242.\nAssistant: Notiert.",
    "recall": "User: What is my card number?\nAssistant: Your card is 4111 1111 1111 4242.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "theatre": "User: Remember that my theatre seat is 4242.\nAssistant: Noted.",
}
_FOUR = ("locker", "card", "phone", "gym")
_TEXTS = ("4242", "card", "phone", "locker code", "code", "card 4242", "gym code")
_EVERY = sorted(forms.words(forms.ALL))
_POOLS = {
    "Oublie": {"casier": "casier", "carte": "carte", "telephone": "téléphone"},
    "Vergiss": {"spind": "Spind", "karte": "Karte", "handy": "Handy"},
    "Olvida": {"gimnasio": "gimnasio", "tarjeta": "tarjeta", "telefono": "teléfono"},
}


async def _forget(query: str, text: str, ids: tuple[str, ...]) -> set[str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        row = MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="a")
        await store.add(row)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return set(ids) - left


async def _deleted(query: str, ids: tuple[str, ...], texts: tuple[str, ...]) -> set[str]:
    gone: set[str] = set()
    for text in texts:
        gone |= await _forget(query, text, ids)
    return gone


@pytest.mark.parametrize("every", _EVERY)
@pytest.mark.parametrize("row", ["card", "phone", "locker"])
async def test_a_row_named_between_a_word_for_all_and_the_value_limits_the_forget(
    every: str, row: str
) -> None:
    query = f"Forget {every} {row} 4242."

    assert not quantifies(query, [_ROWS[name] for name in _FOUR])
    assert await _deleted(query, _FOUR, _TEXTS) == {row}


@pytest.mark.parametrize("every", _EVERY)
@pytest.mark.parametrize("verb", sorted(_POOLS))
async def test_a_row_named_in_another_language_after_a_word_for_all_limits_the_forget(
    every: str, verb: str
) -> None:
    pool = _POOLS[verb]
    for name, word in pool.items():
        gone = await _deleted(f"{verb} {every} {word} 4242.", tuple(pool), ("4242", *pool.values()))

        assert gone == {name}


@pytest.mark.parametrize(
    ("query", "gone"),
    [
        ("Forget every 4242.", {"locker", "card", "phone"}),
        ("Forget all the 4242.", {"locker", "card", "phone"}),
        ("Forget all my 4242.", {"locker", "card", "phone"}),
        ("Forget all of 4242.", {"locker", "card", "phone"}),
        ("Forget all these 4242.", {"locker", "card", "phone"}),
        ("Forget every other 4242.", {"locker", "card", "phone"}),
        ("Forget every single 4242.", {"locker", "card", "phone"}),
        ("Forget 4242 everywhere.", {"locker", "card", "phone"}),
        ("Forget all 4242 except the card.", {"locker", "phone"}),
        ("Forget the card 4242.", {"card"}),
        ("Forget every 4242 on the card.", {"card"}),
        ("Forget every 4242 card.", {"card"}),
        ("Forget every card ending 4242.", {"card"}),
        ("Forget every locker 4242 on the card.", {"card"}),
        ("Forget every locker 4242 except the card.", {"locker"}),
        ("Forget all card 4242, the phone too.", {"card", "phone"}),
    ],
)
async def test_a_word_for_all_with_no_row_named_before_the_value_reads_as_before(
    query: str, gone: set[str]
) -> None:
    assert await _deleted(query, _FOUR, _TEXTS) == gone


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget every 4242.", _FOUR),
        ("Forget all my 4242.", _FOUR),
        ("Forget every other 4242.", _FOUR),
        ("Forget all codes 4242.", _FOUR),
        ("Forget every locker 4242.", ("card", "phone")),
        ("Forget every 4242 card.", _FOUR),
        ("Forget 4242 on every card 7391.", _FOUR),
        ("Oublie tous les 4242.", ("casier", "carte")),
        ("Vergiss alle meine 4242.", ("spind", "karte")),
    ],
)
def test_a_word_for_all_reaches_a_value_past_a_word_naming_no_stored_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert quantifies(query, [_ROWS[name] for name in ids])


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget every card 4242.", ()),
        ("Forget every card 4242.", _FOUR),
        ("Forget every locker 4242.", _FOUR),
        ("Forget all my locker 4242.", _FOUR),
        ("Vergiss jeden Fahrradcode 4242.", ("fahrrad", "karte")),
        ("Forget all card numbers.", _FOUR),
    ],
)
def test_a_word_for_all_stops_at_a_word_naming_a_stored_row_or_a_kind(
    query: str, ids: tuple[str, ...]
) -> None:
    assert not quantifies(query, [_ROWS[name] for name in ids])


def test_a_word_for_all_read_with_no_rows_reaches_a_value_past_any_word() -> None:
    assert quantifies("Forget every card 4242.")


@pytest.mark.parametrize(
    "query",
    ["Forget every 4242 but keep the card.", "Vergiss alle 4242 aber behalte die Karte."],
)
def test_a_word_for_all_before_a_keep_clause_in_its_clause_asks_for_every_row(query: str) -> None:
    assert quantifies(query)


@pytest.mark.parametrize(
    "query",
    [
        "Keep every 4242.",
        "Forget 4242 but keep every card.",
        "Forget all but keep 4242.",
        "Forget every 4242 I keep on the card.",
        "Forget the card but keep all 4242.",
    ],
)
def test_a_word_for_all_inside_a_keep_clause_of_its_clause_is_not_read(query: str) -> None:
    assert not quantifies(query)


async def test_a_row_holding_the_value_only_in_its_reply_is_kept_beside_the_named_row() -> None:
    gone = await _deleted("Forget every locker 4242.", ("locker", "recall"), ("4242",))

    assert gone == {"locker"}


_AFTER = ("4242", "card", "phone", "locker code")


@pytest.mark.parametrize(
    ("query", "ids", "gone"),
    [
        ("Forget the card 4242 everywhere.", _FOUR, {"card"}),
        ("Forget my card 4242 everywhere.", _FOUR, {"card"}),
        ("Forget the card 4242, everywhere.", _FOUR, {"card"}),
        ("Forget the card 4242 all.", _FOUR, {"card"}),
        ("Forget the locker 4242 everywhere.", _FOUR, {"locker"}),
        ("Forget my phone 0721 555 4242 everywhere.", _FOUR, {"phone"}),
        ("Oublie la carte 4242 partout.", ("casier", "carte", "telephone"), {"carte"}),
        ("Oublie le casier 4242, partout.", ("casier", "carte", "telephone"), {"casier"}),
        ("Vergiss die Karte 4242 überall.", ("spind", "karte", "handy"), {"karte"}),
        ("Vergiss den Spind 4242 überall.", ("spind", "karte", "handy"), {"spind"}),
        ("Olvida la tarjeta 4242 en todas partes.", ("gimnasio", "tarjeta"), {"tarjeta"}),
    ],
)
async def test_a_word_for_all_after_a_named_row_and_its_value_lists_the_named_row(
    query: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert not quantifies(query, [_ROWS[name] for name in ids])
    assert quantifies(query)
    assert await _deleted(query, ids, _AFTER) == gone


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget 4242 everywhere.", _FOUR),
        ("Forget the 4242 everywhere.", _FOUR),
        ("Forget the card and 4242 everywhere.", _FOUR),
        ("Forget the card or 4242, everywhere.", _FOUR),
        ("Keep the card, forget 4242 everywhere.", _FOUR),
        ("The card. Forget 4242 everywhere.", _FOUR),
        ("My card is gone so forget 4242 everywhere.", _FOUR),
        ("Forget the bike 4242 everywhere.", _FOUR),
        ("Forget the locker 4242 everywhere.", ("card", "phone")),
        ("0721 555 4242 everywhere, forget it.", _FOUR),
        ("Oublie 4242 partout.", ("casier", "carte", "telephone")),
        ("Vergiss 4242 überall.", ("spind", "karte", "handy")),
        ("Olvida 4242 en todas partes.", ("gimnasio", "tarjeta")),
    ],
)
def test_a_word_for_all_after_a_value_no_row_word_is_before_asks_for_every_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert quantifies(query, [_ROWS[name] for name in ids])


@pytest.mark.parametrize(
    "query",
    ["Forget 4242 everywhere.", "Forget the 4242 everywhere.", "Forget the card and 4242 all."],
)
async def test_a_word_for_all_after_a_value_alone_lists_every_row_holding_it(query: str) -> None:
    assert await _deleted(query, _FOUR, _AFTER) == {"locker", "card", "phone"}


_FRENCH = ("casier", "carte", "telephone")
_GERMAN = ("spind", "karte", "handy")


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget all lockers 4242.", _FOUR),
        ("Forget every lockers 4242.", _FOUR),
        ("Forget all my lockers 4242.", _FOUR),
        ("Forget the lockers 4242 everywhere.", _FOUR),
        ("Oublie tous les casiers 4242.", _FRENCH),
        ("Oublie toutes casiers 4242.", _FRENCH),
        ("Vergiss alle Spinde 4242.", _GERMAN),
        ("Vergiss jeden Spindes 4242.", _GERMAN),
        ("Olvida todas gimnasios 4242.", ("gimnasio", "tarjeta", "telefono")),
        ("Uită all dulapul 4242.", ("dulap", "cardul")),
        ("Uită dulapul 4242 everywhere.", ("dulap", "cardul")),
    ],
)
async def test_a_word_for_all_stops_at_a_longer_form_of_a_stored_row_word(
    query: str, ids: tuple[str, ...]
) -> None:
    assert not quantifies(query, [_ROWS[name] for name in ids])
    assert await _deleted(query, ids, ("4242", "card", "phone", "Karte", "carte")) == set()


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget every single 4242.", _FOUR),
        ("Forget every other 4242.", _FOUR),
        ("Forget all the 4242.", ("theatre", "card")),
        ("Forget all these 4242.", ("theatre", "card")),
        ("Forget every lock 4242.", _FOUR),
        ("Forget all lockers 4242.", ("card", "phone")),
        ("Forget all cupboards 4242.", _FOUR),
        ("Vergiss alle meine 4242.", _GERMAN),
        ("Oublie tous les 4242.", _FRENCH),
    ],
)
def test_a_word_for_all_reaches_a_value_past_a_word_no_stored_row_word_starts(
    query: str, ids: tuple[str, ...]
) -> None:
    assert quantifies(query, [_ROWS[name] for name in ids])


async def test_a_word_a_row_word_does_not_start_still_lists_every_row() -> None:
    gone = await _deleted("Forget all the 4242.", ("theatre", "card", "phone"), ("4242",))

    assert gone == {"theatre", "card", "phone"}
