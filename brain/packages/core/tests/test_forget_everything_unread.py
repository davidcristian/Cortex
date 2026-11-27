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
from cortex_core.forget_every import everything
from cortex_core.forget_unnamed import KEPT_ALL
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 15, 9, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "gym": "User: Remember that my gym opens at noon.\nAssistant: Noted.",
    "address": "User: Remember that my address is Elm Street.\nAssistant: Noted.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "tarjeta": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "dulap": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
}
_THREE = ("locker", "card", "phone")
_TEXTS = {"locker": "locker code", "karte": "Karte", "spind": "Spind"}


async def _forget(query: str, text: str, ids: tuple[str, ...]) -> tuple[set[str], str]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        row = MemoryRecord(id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="a")
        await store.add(row)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    result = await tool.invoke(call)
    left = {hit.record.id for hit in await store.search((1.0, 0.0), k=10)}
    return set(ids) - left, result.content


async def _deleted(query: str, ids: tuple[str, ...] = _THREE) -> set[str]:
    gone: set[str] = set()
    for text in (*(_TEXTS.get(name, name) for name in ids), "4242", "code"):
        gone |= (await _forget(query, text, ids))[0]
    return gone


@pytest.mark.parametrize(
    ("query", "ids", "gone"),
    [
        ("Forget everything.", _THREE, {"locker", "card", "phone"}),
        ("Forget everything but my card.", _THREE, {"locker", "phone"}),
        ("Forget everything except my card.", _THREE, {"locker", "phone"}),
        ("Forget everything, also the card.", _THREE, {"locker", "card", "phone"}),
        ("Forget everything, my card too.", _THREE, {"locker", "card", "phone"}),
        ("Forget everything on my card.", _THREE, {"card"}),
        ("Forget everything about my gym.", ("gym", "card"), {"gym"}),
        ("Forget everything about my stay.", _THREE, {"locker", "card", "phone"}),
        ("Forget everything I told you today.", _THREE, {"locker", "card", "phone"}),
        ("Forget all of that.", _THREE, {"locker", "card", "phone"}),
        ("Forget the card that stays in my wallet.", _THREE, {"card"}),
        ("Forget all my card numbers.", _THREE, {"card"}),
        ("Delete all of my card details from memory.", _THREE, {"card"}),
        ("Forget everything on my card please.", _THREE, {"card"}),
        ("Forget all of my card details.", _THREE, {"card"}),
        ("Delete all of my locker code from memory.", _THREE, {"locker"}),
        ("Forget everything on my card and my phone.", _THREE, {"card", "phone"}),
        ("Forget what stays the same.", _THREE, {"locker", "card", "phone"}),
        ("Do not forget everything, my card stays.", _THREE, set[str]()),
        ("Everything fine, forget my card.", _THREE, {"card"}),
        ("Forget everything else.", _THREE, {"locker", "card", "phone"}),
        ("Forget everything else about my card.", _THREE, {"card"}),
        ("Forget everything else, also the card.", _THREE, {"card"}),
        ("Oublie tout sauf la carte.", ("casier", "carte"), {"casier"}),
        ("Vergiss alle, die Karte bleibt.", ("spind", "karte"), set[str]()),
        ("Olvida todas excepto la tarjeta.", ("gimnasio", "tarjeta"), {"gimnasio"}),
        ("Olvida todo sobre la tarjeta.", ("gimnasio", "tarjeta"), {"tarjeta"}),
        ("Vergeet 4242 tot morgen.", _THREE, set[str]()),
        ("Forget my todo list.", _THREE, {"locker", "card", "phone"}),
        ("Wipe everything, the card too.", _THREE, {"locker", "card", "phone"}),
        ("Wipe everything, and the card.", _THREE, {"locker", "card", "phone"}),
        ("Wipe the card, the phone as well.", _THREE, {"card", "phone"}),
        (
            "Forget the locker code, the phone and the card too.",
            _THREE,
            {"locker", "card", "phone"},
        ),
        ("My card is old, forget it.", _THREE, {"card"}),
        ("Forget all card numbers.", _THREE, {"card"}),
        ("Forget every card.", _THREE, {"card"}),
        ("Forget my old card.", _THREE, {"card"}),
        ("Forget my gym locker code and my phone.", _THREE, {"locker", "phone"}),
        ("Forget everything about my card.", _THREE, {"card"}),
        ("Vergiss alles von der Karte.", ("spind", "karte"), {"karte"}),
        ("Olvida todo de la tarjeta.", ("gimnasio", "tarjeta"), {"tarjeta"}),
        ("Forget all of my card numbers.", _THREE, {"card"}),
        ("Forget all of the card.", _THREE, {"card"}),
        ("Forget everything of my card.", _THREE, {"card"}),
        ("Forget it all on my card.", _THREE, {"card"}),
    ],
)
async def test_a_forget_of_everything_in_a_form_a_reader_reads_lists_what_it_listed(
    query: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert await _deleted(query, ids) == gone


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget everything, my card stays.", _THREE),
        ("Forget everything, leave my card.", _THREE),
        ("Forget everything, the card stays, the phone too.", _THREE),
        ("Forget everything, the card stays, only the card.", _THREE),
        ("Forget everything apart from the card.", _THREE),
        ("Forget everything. My card stays.", _THREE),
        ("Forget everything and my card stays.", _THREE),
        ("Delete all of it, my card stays.", _THREE),
        ("Forget everything, my locker code stays.", _THREE),
        ("Forget everything, the code stays.", _THREE),
        ("Forget everything, my card 4242 stays.", _THREE),
        ("Oublie tout, la carte reste.", ("casier", "carte")),
        ("Oublie tout, laisse la carte.", ("casier", "carte")),
        ("Oublie tout à part la carte.", ("casier", "carte")),
        ("Vergiss alle, lass die Karte.", ("spind", "karte")),
        ("Vergiss alle bis auf die Karte.", ("spind", "karte")),
        ("Olvida todas, la tarjeta se queda.", ("gimnasio", "tarjeta")),
        ("Olvida todas, deja la tarjeta.", ("gimnasio", "tarjeta")),
        ("Forget everything, la carte stays.", ("casier", "carte")),
        ("Forget everything on my card, la carte stays.", _THREE),
        ("Forget everything apart from my address, 4242 that is.", (*_THREE, "address")),
        ("Forget everything from today, my card stays.", _THREE),
        ("Forget everything else, my card stays.", _THREE),
        ("Forget all else. My card stays.", _THREE),
        ("Forget everything the card stays.", _THREE),
        ("Forget everything my card stays.", _THREE),
        ("Forget about everything the card stays.", _THREE),
        ("Wipe everything the card stays.", _THREE),
        ("Wipe everything apart from the card.", _THREE),
        ("Oublie tout la carte reste.", ("casier", "carte")),
        ("Vergiss alles bis auf die Karte.", ("spind", "karte")),
        ("Alles muss weg bis auf die Karte.", ("spind", "karte")),
        ("Olvida todo la tarjeta se queda.", ("gimnasio", "tarjeta")),
        ("Uită tot în afară de cardul.", ("dulap", "cardul")),
        ("Forget all of it the card stays.", _THREE),
        ("Forget all of them the card stays.", _THREE),
        ("Delete all of it the card stays.", _THREE),
        ("Forget it all the card stays.", _THREE),
        ("Forget everything of mine the card stays.", _THREE),
        ("Forget everything on it the card stays.", _THREE),
        ("Forget everything card stays.", _THREE),
        ("Forget all of my card the phone stays.", _THREE),
        ("Forget everything, only the card.", _THREE),
        ("Forget everything, just the phone.", _THREE),
        ("Delete all of it, only the locker.", _THREE),
        ("Oublie tout, seulement la carte.", ("casier", "carte")),
        ("Forget the card, forget everything, only the phone.", _THREE),
    ],
)
async def test_a_forget_of_everything_naming_a_row_in_a_form_no_reader_reads_keeps_every_row(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _deleted(query, ids) == set()


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget everything my card holds.", _THREE),
        ("Forget all my card numbers but quickly.", _THREE),
        ("Uită tot despre cardul.", ("dulap", "cardul")),
    ],
)
async def test_a_forget_of_everything_differing_from_a_kept_form_by_an_unread_word_keeps_it(
    query: str, ids: tuple[str, ...]
) -> None:
    assert await _deleted(query, ids) == set()


@pytest.mark.parametrize(
    ("query", "ids", "gone"),
    [
        ("Wipe everything, my card stays.", _THREE, {"locker", "phone"}),
        ("Wipe everything, leave the card.", _THREE, {"locker", "phone"}),
        ("Clear everything. The card stays.", _THREE, {"locker", "phone"}),
        ("Everything must go, my card stays.", _THREE, set[str]()),
        ("Vide tout, la carte reste.", ("casier", "carte"), {"casier"}),
        ("Alles muss weg, die Karte bleibt.", ("spind", "karte"), set[str]()),
        ("Todo fuera, la tarjeta se queda.", ("gimnasio", "tarjeta"), set[str]()),
        ("Olvida todo, la tarjeta se queda.", ("gimnasio", "tarjeta"), set[str]()),
        ("Uită tot, cardul rămâne.", ("dulap", "cardul"), set[str]()),
        ("Forget my locker code, my card stays.", _THREE, {"locker"}),
        ("Wipe everything, the card stays, don't delete the phone.", _THREE, set[str]()),
        ("Wipe everything, the card stays. Do not forget the phone.", _THREE, set[str]()),
        ("Wipe everything but don't erase the phone, the card stays.", _THREE, set[str]()),
        ("Vide tout, la carte reste, n'efface pas le casier.", ("casier", "carte"), set[str]()),
        ("Uită tot, cardul rămâne, nu șterge dulapul.", ("dulap", "cardul"), set[str]()),
    ],
)
async def test_a_row_a_later_clause_names_in_a_role_no_reader_reads_is_kept(
    query: str, ids: tuple[str, ...], gone: set[str]
) -> None:
    assert await _deleted(query, ids) == gone


@pytest.mark.parametrize(
    ("query", "ids", "kept"),
    [
        ("Forget the card. Forget everything the phone stays.", _THREE, "phone"),
        ("Forget my old card. Forget all of it the phone stays.", _THREE, "phone"),
        ("Forget the phone, forget all of it the card stays.", _THREE, "card"),
        ("Delete the locker. Delete it all the card stays.", _THREE, "card"),
        ("Wipe the card; forget everything the locker stays.", _THREE, "locker"),
        ("Oublie le casier, oublie tout la carte reste.", ("casier", "carte"), "carte"),
        ("Vergiss den Spind. Vergiss alles die Karte bleibt.", ("spind", "karte"), "karte"),
        ("Borra el gimnasio, olvida todo la tarjeta se queda.", ("gimnasio", "tarjeta"), "tarjeta"),
        ("Uită dulapul. Uită tot cardul rămâne.", ("dulap", "cardul"), "cardul"),
    ],
)
async def test_a_row_kept_after_a_forget_of_everything_behind_another_forget_clause_is_kept(
    query: str, ids: tuple[str, ...], kept: str
) -> None:
    assert kept not in await _deleted(query, ids)


@pytest.mark.parametrize(
    "query",
    [
        "Forget everything the card stays. Delete the phone.",
        "Forget it all the card stays, wipe 4242.",
    ],
)
async def test_a_row_kept_after_a_forget_of_everything_before_another_forget_clause_is_kept(
    query: str,
) -> None:
    assert "card" not in await _deleted(query)


@pytest.mark.parametrize(
    ("query", "gone"),
    [
        ("Forget the card. Forget everything.", {"locker", "card", "phone"}),
        ("Forget the card, then forget everything on my phone.", {"card", "phone"}),
        ("Forget the card. Forget everything, the phone stays.", set[str]()),
        ("Forget the card. Forget the phone.", {"card", "phone"}),
    ],
)
async def test_a_forget_of_everything_behind_another_forget_clause_lists_what_it_listed(
    query: str, gone: set[str]
) -> None:
    assert await _deleted(query) == gone


async def test_a_forget_of_everything_keeping_every_row_says_each_was_kept() -> None:
    gone, said = await _forget("Forget everything, my card stays.", "card", _THREE)
    assert (gone, said) == (set(), f"{KEPT_ALL}.")


_LIMITED = "Forget everything on my card, the phone stays."
_NUMBERS = "Forget all my card numbers, the phone stays."


@pytest.mark.parametrize(
    ("query", "text", "gone"),
    [
        (_LIMITED, "card", {"card"}),
        (_LIMITED, "phone", set[str]()),
        (_LIMITED, "locker code", set[str]()),
        (_LIMITED, "4242", {"card"}),
        (_NUMBERS, "card", {"card"}),
        (_NUMBERS, "phone", set[str]()),
    ],
)
async def test_a_read_limit_beside_a_row_in_an_unread_form_lists_only_the_limit(
    query: str, text: str, gone: set[str]
) -> None:
    assert (await _forget(query, text, _THREE))[0] == gone


@pytest.mark.parametrize(
    ("query", "place"),
    [
        ("Forget everything, my card stays.", (0, 1)),
        ("Please delete all of it.", (0, 2)),
        ("All good, forget everything.", (1, 1)),
        ("Forget everything about my gym.", None),
        ("Forget everything else, my card stays.", (0, 1)),
        ("Forget everything else.", (0, 1)),
        ("Forget everything else today.", None),
        ("Forget all 4242, card stays.", None),
        ("Do not forget everything.", None),
        ("Everything fine, forget my card.", None),
        ("All of you forget my card.", None),
        ("Forget my card.", None),
    ],
)
def test_the_word_for_all_of_a_forget_of_everything_is_found(
    query: str, place: tuple[int, int] | None
) -> None:
    assert everything(query) == place
