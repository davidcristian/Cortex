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
from cortex_core.forget_clauses import asking, parts
from cortex_core.forget_inside import INSIDE_LINE
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 13, 6, 0, 0, tzinfo=UTC)
_ROWS = {
    "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
    "casier": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
    "spind": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
    "gimnasio": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
    "gym": "User: Remember that my gym code is 4242.\nAssistant: Noted.",
    "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "visa": "User: Remember that my Visa card is 4111 1111 1111 4242.\nAssistant: Noted.",
    "carte": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
    "telephone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    "karte": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
    "handy": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    "cardul": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
    "telefonul": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
    "cartela": "User: Ține minte că cartela mea este 4111 1111 1111 4242.\nAssistant: Notat.",
}


async def _forget(query: str, *ids: str) -> tuple[str | None, str, list[str]]:
    store = InMemoryMemoryStore()
    for i, name in enumerate(ids):
        at = _AT + timedelta(minutes=i)
        record = MemoryRecord(
            id=name, text=_ROWS[name], embedding=(1.0, 0.0), at=at, session_id="chat-a"
        )
        await store.add(record)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "4242"}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return card, result.content, left


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget the locker code 4242 that I texted from my phone.", ("locker", "phone")),
        ("Oublie le code 4242 du casier que j'ai envoyé par téléphone.", ("casier", "phone")),
        ("Oublie le code 4242 du casier, il est noté sur la carte du parc.", ("casier", "card")),
        (
            "Vergiss den Code 4242 vom Spind, er steht auf meiner Karte fürs Konzert.",
            ("spind", "card"),
        ),
        ("Olvida el código 4242 del gimnasio, lo escribí en la tarjeta.", ("gimnasio", "card")),
        ("Forget my gym code 4242, the one written on the birthday card.", ("gym", "card")),
        ("I texted it from my phone: forget the locker code 4242.", ("locker", "phone")),
    ],
)
async def test_a_row_named_only_in_a_remark_about_the_value_is_kept_and_shown(
    query: str, ids: tuple[str, ...]
) -> None:
    card, result, left = await _forget(query, *ids)
    assert left == [ids[1]]
    assert card is not None
    assert card.split(INSIDE_LINE)[1].count("4242") == 1
    assert "1 other remembered exchanges contain that text only inside a longer value" in result


@pytest.mark.parametrize(
    "query",
    [
        "Forget the locker code 4242 and the card, I texted both from my phone.",
        "Forget the card and the locker code 4242, I read both on my phone.",
        "Forget the locker code 4242 and my card, the ones I sent from my phone.",
    ],
)
async def test_a_row_only_a_remark_names_is_kept_beside_a_card_word_that_asks(query: str) -> None:
    card, result, left = await _forget(query, "locker", "card", "phone")
    assert left == ["phone"]
    assert card is not None
    assert "0721 555 4242" in card.split(INSIDE_LINE)[1]
    assert "1111 4242" not in card.split(INSIDE_LINE)[1]
    assert "1 other remembered exchanges contain that text only inside a longer value" in result


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget the card 4242, the one I read from my phone.", ("card", "phone"), ["phone"]),
        ("Forget the card 4242 that I read from my phone.", ("card", "phone"), ["phone"]),
        (
            "Forget 4242 and my card, I sent the code from my phone.",
            ("locker", "card", "phone"),
            ["locker", "phone"],
        ),
    ],
)
async def test_a_row_only_a_remark_names_is_kept_beside_a_row_holding_the_value_as_a_group(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, result, rows = await _forget(query, *ids)
    assert rows == left
    assert card is not None
    listed, kept = card.split(INSIDE_LINE)
    assert "4111 1111 1111 4242" in listed
    assert "0721 555 4242" in kept
    assert "0721 555 4242" not in listed
    assert result.startswith("forgot 1 remembered exchanges;")


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget my card 4242.", ("card", "phone"), ["phone"]),
        ("Forget my card ending 4242.", ("card", "phone", "locker"), ["locker", "phone"]),
        ("Forget the card 4242 and my phone.", ("card", "phone"), []),
        ("Forget the locker code 4242 and the card, the Visa one.", ("locker", "visa"), []),
    ],
)
async def test_a_card_word_where_the_message_asks_still_lists_the_card(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert "4111 1111 1111 4242" in card.split(INSIDE_LINE)[0]
    assert rows == left


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Forget my phone and card numbers ending 4242.", ("gym", "phone", "card"), ["gym"]),
        ("Forget the locker code 4242 and my phone number ending 4242.", ("locker", "phone"), []),
        ("Forget the locker code 4242, and the card one too.", ("locker", "card"), []),
        ("Forget the locker code 4242 and the phone that ends in 4242.", ("locker", "phone"), []),
        (
            "Forget that my locker code is 4242 and my phone is 0721 555 4242.",
            ("locker", "phone"),
            [],
        ),
        ("Forget the locker code 4242 and the card, I texted both.", ("locker", "card"), []),
        ("Forget 4242 that I texted from my phone.", ("locker", "phone"), ["locker"]),
        ("Forget 4242, it is the end of my phone number.", ("locker", "phone"), ["locker"]),
        ("Forget the card 4242 from my phone.", ("card", "phone"), []),
        ("Forget the card 4242, and the phone too.", ("card", "phone"), []),
    ],
)
async def test_a_row_named_where_the_message_asks_to_forget_is_still_listed(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert INSIDE_LINE not in card
    assert rows == left


@pytest.mark.parametrize(
    ("query", "text", "asked"),
    [
        ("Forget the code 4242 that I sent.", "4242", "forget the code 4242"),
        ("Forget that my code is 4242.", "4242", "forget that my code is 4242"),
        ("Forget 4242, it is on my card.", "4242", "forget 4242"),
        ("Forget 4242, and the card.", "4242", "forget 4242 and the card"),
        ("Forget 4242, not the card.", "4242", "forget 4242 not the card"),
        ("It is on my card, 0721 555 4242.", "0721 555 4242", "0721 555 4242"),
        ("Forget the code 42 42 that I sent.", "4242", "forget the code 42 42 that i sent"),
        ("Forget my code.", "", "forget my code"),
    ],
)
def test_asking_reads_the_message_less_each_remark(query: str, text: str, asked: str) -> None:
    assert asking(query, text) == asked


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        (
            "Forget my locker code 4242, the card one as well.",
            ("locker", "card", "phone"),
            ["phone"],
        ),
        ("Forget my locker code 4242, also my phone.", ("locker", "card", "phone"), ["card"]),
        (
            "Forget the locker code 4242 and the card, my phone as well.",
            ("locker", "card", "phone"),
            [],
        ),
        (
            "Forget the locker code 4242 and the card, the phone too.",
            ("locker", "card", "phone"),
            [],
        ),
        (
            "Forget the locker code 4242 and the card, plus my phone.",
            ("locker", "card", "phone"),
            [],
        ),
        ("Forget the card 4242, my phone as well.", ("card", "phone"), []),
        ("Forget the card 4242. My phone as well.", ("card", "phone"), []),
        ("Forget the card 4242, the phone one too.", ("card", "phone"), []),
        (
            "Oublie le code 4242 du casier, la carte aussi.",
            ("casier", "carte", "telephone"),
            ["telephone"],
        ),
        ("Oublie la carte 4242, mon téléphone aussi.", ("carte", "telephone"), []),
        (
            "Vergiss den Code 4242 vom Spind, die Karte auch.",
            ("spind", "karte", "handy"),
            ["handy"],
        ),
        ("Vergiss die Karte 4242, mein Handy auch.", ("karte", "handy"), []),
    ],
)
async def test_a_clause_adding_a_named_row_to_a_forget_lists_the_row(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert rows == left
    listed = card.split("\nKept", 1)[0]
    assert all((_ROWS[name].split("\n")[0][6:] in listed) != (name in left) for name in ids)


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget the card 4242, my phone stays.", ("card", "phone")),
        ("Forget the card 4242, my phone is new.", ("card", "phone")),
        ("Forget the card 4242, not my phone.", ("card", "phone")),
        ("Forget the card 4242, my phone has it too.", ("card", "phone")),
        ("Forget the card 4242, my phone too has it.", ("card", "phone")),
        ("Forget the card 4242, my phone is too old.", ("card", "phone")),
        ("Forget the card 4242, keep my phone as well.", ("card", "phone")),
        ("Forget the card 4242, leave my phone too.", ("card", "phone")),
        ("Forget the card 4242, remember my phone too.", ("card", "phone")),
        ("Forget the card 4242, leave phone too.", ("card", "phone")),
        ("Oublie la carte 4242, mon téléphone reste.", ("carte", "telephone")),
        ("Oublie la carte 4242, mon téléphone est neuf.", ("carte", "telephone")),
        ("Oublie la carte 4242, pas mon téléphone.", ("carte", "telephone")),
        ("Oublie la carte 4242, mon téléphone l'a aussi.", ("carte", "telephone")),
        ("Oublie la carte 4242, garde mon téléphone aussi.", ("carte", "telephone")),
        ("Vergiss die Karte 4242, mein Handy ist neu.", ("karte", "handy")),
        ("Vergiss die Karte 4242, nicht mein Handy.", ("karte", "handy")),
        ("Vergiss die Karte 4242, mein Handy hat sie auch.", ("karte", "handy")),
        ("Vergiss die Karte 4242, mein Handy ist auch alt.", ("karte", "handy")),
        ("Vergiss die Karte 4242, mein Handy ist auch.", ("karte", "handy")),
        ("Oublie la carte 4242, mon téléphone est aussi.", ("carte", "telephone")),
        ("Vergiss die Karte 4242, behalte mein Handy auch.", ("karte", "handy")),
    ],
)
async def test_a_remark_or_keep_clause_naming_a_row_beside_a_forget_keeps_the_row(
    query: str, ids: tuple[str, str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert rows == [ids[1]]
    assert _ROWS[ids[1]].split("\n")[0][6:] in card.split("\nKept", 1)[1]


@pytest.mark.parametrize(
    ("query", "named", "asked"),
    [
        ("Forget 4242, my phone too.", {"phone"}, "forget 4242 my phone too"),
        ("Forget 4242, also the card one.", {"card"}, "forget 4242 also the card one"),
        ("Forget 4242, my phone too.", {"card"}, "forget 4242"),
        ("Forget 4242, my phone.", {"phone"}, "forget 4242"),
        ("Forget 4242, my phone too too.", {"phone"}, "forget 4242"),
        ("Forget 4242, my phone as.", {"phone"}, "forget 4242"),
        ("Forget 4242, phone too.", {"phone"}, "forget 4242"),
        ("Forget 4242, also my phone too.", {"phone"}, "forget 4242"),
        ("Forget 4242, the one too.", {"phone"}, "forget 4242"),
    ],
)
def test_asking_reads_a_clause_adding_a_named_row(query: str, named: set[str], asked: str) -> None:
    assert asking(query, "4242", frozenset(named)) == asked


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Vergiss die Karte 4242, mein Handy bleibt.", ("karte", "handy"), ["handy"]),
        ("Vergiss die Karte 4242, das Handy bleibt.", ("karte", "handy"), ["handy"]),
        ("Vergiss die Karte 4242, das Handy behalte ich.", ("karte", "handy"), ["handy"]),
        ("Vergiss die Karte 4242 aber mein Handy bleibt.", ("karte", "handy"), ["handy"]),
        ("Forget the card 4242, my phone I keep.", ("card", "phone"), ["phone"]),
        ("Forget the card 4242 but my phone I keep.", ("card", "phone"), ["phone"]),
        (
            "Forget the card 4242, the locker and my phone I keep.",
            ("locker", "card", "phone"),
            ["phone"],
        ),
        ("Oublie la carte 4242, mon téléphone je le garde.", ("carte", "telephone"), ["telephone"]),
        ("Uită cardul 4242, telefonul îl păstrez.", ("cardul", "telefonul"), ["telefonul"]),
        ("Uită cardul 4242 dar telefonul îl păstrez.", ("cardul", "telefonul"), ["telefonul"]),
        ("Uită cardul 4242, cartela o păstrez.", ("cardul", "cartela"), ["cartela"]),
        ("Uită cardul 4242 dar cartela mea o păstrez.", ("cardul", "cartela"), ["cartela"]),
    ],
)
async def test_a_row_named_before_its_keep_verb_is_kept(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    card, _, rows = await _forget(query, *ids)
    assert card is not None
    assert rows == left
    listed = card.split("\nKept", 1)[0]
    assert all((_ROWS[name].split("\n")[0][6:] in listed) != (name in left) for name in ids)


@pytest.mark.parametrize(
    ("query", "ids", "left"),
    [
        ("Vergiss die Karte 4242, mein Handy vergiss auch.", ("karte", "handy"), []),
        ("Forget the card 4242, my phone forget too.", ("card", "phone"), []),
        ("Forget the card 4242 and keep my phone.", ("card", "phone"), ["phone"]),
        ("Forget 4242, the card and keep my phone.", ("card", "phone"), ["phone"]),
        ("Vergiss die Karte 4242 und behalte mein Handy.", ("karte", "handy"), ["handy"]),
        ("Uită cardul 4242 și păstrează telefonul.", ("cardul", "telefonul"), ["telefonul"]),
        ("Oublie la carte 4242 mais garde mon téléphone.", ("carte", "telephone"), ["telephone"]),
    ],
)
async def test_a_row_named_after_its_forget_verb_is_still_listed_beside_a_keep_verb(
    query: str, ids: tuple[str, ...], left: list[str]
) -> None:
    _, _, rows = await _forget(query, *ids)
    assert rows == left


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Vergiss die Karte 4242 mein Handy bleibt.", ("karte", "handy")),
        ("Forget the card 4242 my phone I keep.", ("card", "phone")),
    ],
)
async def test_a_keep_verb_after_a_forget_verb_with_no_joining_word_keeps_both_rows(
    query: str, ids: tuple[str, str]
) -> None:
    card, result, rows = await _forget(query, *ids)
    assert card is None
    assert rows == sorted(ids)
    assert result.startswith("nothing was forgotten")


@pytest.mark.parametrize(
    ("query", "forget", "keep"),
    [
        ("Forget the card 4242 my phone I keep.", "forget", "the card 4242 my phone i keep"),
        ("Vergiss die Karte, mein Handy bleibt.", "vergiss die karte", "mein handy bleibt"),
        ("Forget the card and keep the phone.", "forget the card", "and keep the phone"),
        ("Keep the phone and forget the card.", "forget the card", "keep the phone and"),
        ("Uită cardul, cartela o păstrez.", "uită cardul", "cartela o păstrez"),
    ],
)
def test_parts_reads_a_keep_verb_back_to_a_forget_verb_or_a_joining_word(
    query: str, forget: str, keep: str
) -> None:
    assert tuple(" ".join(tokens) for tokens in parts(query)) == (forget, keep)


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Forget the card 4242, keep the locker, my phone too.", ("card", "locker", "phone")),
        ("Forget the card 4242, keep the locker, the phone as well.", ("card", "locker", "phone")),
        ("Forget the card 4242, I keep the locker, also my phone.", ("card", "locker", "phone")),
        ("Forget the card 4242, not the locker, my phone too.", ("card", "locker", "phone")),
        ("Forget the card 4242, except the locker, my phone too.", ("card", "locker", "phone")),
        (
            "Forget the card 4242, don't forget the locker, my phone too.",
            ("card", "locker", "phone"),
        ),
        (
            "Forget the locker code 4242, keep the gym, my phone too, the card as well.",
            ("locker", "gym", "phone", "card"),
        ),
        (
            "Oublie la carte 4242, garde le casier, mon téléphone aussi.",
            ("carte", "casier", "telephone"),
        ),
        (
            "Vergiss die Karte 4242, behalte den Spind, mein Handy auch.",
            ("karte", "spind", "handy"),
        ),
        ("Vergiss die Karte 4242, der Spind bleibt, mein Handy auch.", ("karte", "spind", "handy")),
    ],
)
async def test_a_clause_adding_a_row_after_a_keep_clause_keeps_the_row(
    query: str, ids: tuple[str, ...]
) -> None:
    _, _, rows = await _forget(query, *ids)
    assert rows == sorted(ids[1:])


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        (
            "Forget the card 4242, keep the locker, forget my phone too.",
            ("card", "locker", "phone"),
        ),
        ("Keep the locker, forget the card 4242, my phone too.", ("card", "locker", "phone")),
    ],
)
async def test_a_clause_adding_a_row_after_a_forget_clause_still_lists_the_row(
    query: str, ids: tuple[str, ...]
) -> None:
    _, _, rows = await _forget(query, *ids)
    assert rows == ["locker"]
