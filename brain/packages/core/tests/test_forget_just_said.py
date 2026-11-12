from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_unnamed import (
    KEPT_ALL,
    KEPT_LINE,
    KEPT_NOTE,
    KEPT_NOTES,
    KeptRows,
    kept_note,
    unnamed,
)
from cortex_core.stops import StopLedger
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 9, 2, 0, 0, tzinfo=UTC)
_POOL = "User: My locker code at the pool is 7319.\nAssistant: Got it, 7319."
_BIKE = "User: My bike lock code is also 7319.\nAssistant: Noted."
_VELO = "User: Le code de mon cadenas de vélo est 5937, retiens-le.\nAssistant: C'est noté."
_GYM = "User: Remember that my gym locker number is 5521.\nAssistant: I've noted that."
_SHED = "User: Remember that the shed padlock code is also 5521.\nAssistant: Noted."
_JUST = "Actually, forget what I just told you."


def _record(record_id: str, text: str, session_id: str | None, minutes: int) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope="global",
        session_id=session_id,
    )


async def _forget(
    text: str, query: str, *rows: tuple[str, str, str | None]
) -> tuple[str | None, str, list[str]]:
    store = InMemoryMemoryStore()
    for minutes, (record_id, row, session_id) in enumerate(rows):
        await store.add(_record(record_id, row, session_id, minutes))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    card = await tool.card(call)
    result = await tool.invoke(call)
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return card, result.content, left


@pytest.mark.parametrize(
    ("text", "query", "row"),
    [
        ("7319", _JUST, _POOL),
        ("5937", "Oublie ce que je viens de te dire.", _VELO),
    ],
)
async def test_a_forget_of_what_was_just_said_deletes_the_row_the_chat_stored(
    text: str, query: str, row: str
) -> None:
    card, _, left = await _forget(text, query, ("said", row, "chat-a"))
    assert card is not None
    assert KEPT_LINE not in card
    assert left == []


async def test_a_row_another_chat_stored_is_still_kept_when_the_message_names_nothing() -> None:
    card, said, left = await _forget("7319", _JUST, ("bike", _BIKE, "chat-b"))
    assert (card, said, left) == (None, f"{KEPT_ALL}.", ["bike"])


async def test_only_the_newest_row_the_chat_stored_is_listed_beside_other_chats_rows() -> None:
    rows = [("old", _POOL, "chat-a"), ("pool", _POOL, "chat-a"), ("bike", _BIKE, "chat-b")]
    card, _, left = await _forget("7319", _JUST, *rows)
    assert card is not None
    assert card.splitlines()[0] == "Deletes for good, with no undo, these 1 remembered exchanges:"
    assert left == ["bike", "old"]


async def test_the_padlock_the_chat_just_stored_is_kept_on_a_forget_naming_the_gym() -> None:
    rows = [("gym", _GYM, "chat-g"), ("shed", _SHED, "chat-a")]
    card, _, left = await _forget("5521", "Forget my gym locker number.", *rows)
    assert card is not None
    assert KEPT_LINE in card
    assert left == ["shed"]


async def test_a_word_of_a_row_the_turn_deleted_keeps_the_newest_row_of_the_chat() -> None:
    rows = [_record("shed", _SHED, "chat-a", 1)]
    gym = _record("gym", _GYM, "chat-a", 0)
    kept = unnamed(rows, "5521", "Forget my gym locker number.", (gym,), "chat-a")
    assert [record.id for record in kept] == ["shed"]


def test_no_calling_chat_reads_no_row_as_just_said() -> None:
    rows = [_record("pool", _POOL, None, 0)]
    assert [record.id for record in unnamed(rows, "7319", _JUST)] == ["pool"]


async def _kept_after(
    texts: tuple[str, ...], *rows: tuple[str, str, str | None]
) -> tuple[str, ...]:
    store = InMemoryMemoryStore()
    for minutes, (record_id, row, session_id) in enumerate(rows):
        await store.add(_record(record_id, row, session_id, minutes))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    kept: tuple[str, ...] | None = None
    for index, text in enumerate(texts):
        stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=_JUST)
        arguments = {"text": text}
        call = ToolCall(
            id=f"c{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments=arguments, stamp=stamp
        )
        await tool.card(call)
        kept = (await tool.invoke(call)).kept
    assert kept is not None
    return kept


async def test_a_forget_that_keeps_every_row_reports_their_excerpts() -> None:
    kept = await _kept_after(("7319",), ("bike", _BIKE, "chat-b"))
    assert len(kept) == 1
    assert "bike lock code is also 7319" in kept[0]


async def test_a_later_call_deleting_the_kept_row_reports_none_kept() -> None:
    assert await _kept_after(("7319", "bike lock"), ("bike", _BIKE, "chat-b")) == ()


def test_the_kept_note_names_each_row_and_asks_for_no_forget() -> None:
    note = kept_note(("first row", "second row"))
    assert note == f"{KEPT_NOTE}\n- first row\n- second row)"
    assert "forget" not in note.lower()


def test_kept_rows_hold_a_bounded_number_of_turns() -> None:
    rows = KeptRows()
    for turn in range(40):
        rows.keep(f"t{turn}", {"r": f"row {turn}"})
    rows.drop("t1", ["other"])
    rows.drop("t39", ["r"])
    assert (rows.held("t0"), rows.held("t8"), rows.held("t39")) == ((), ("row 8",), ())


@pytest.mark.parametrize(
    ("kept", "closed"), [((), "Done."), (("a row",), f"Done.{KEPT_NOTE}\n- a row)")]
)
def test_a_reply_after_a_kept_row_closes_with_the_kept_note(
    kept: tuple[str, ...], closed: str
) -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = ["Done."]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_kept=kept)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=_JUST))
    assert "".join(parts) == closed


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie 7319, mais garde celui du cabanon, merci.", "fr"),
        ("Vergiss 7319, behalte den vom Schuppen.", "de"),
        ("Olvida 7319, guarda el del cobertizo, por favor.", "es"),
        ("Uită 7319, păstrează-l pe cel de la magazie.", "ro"),
        ("Forget 7319, keep the shed one.", "en"),
    ],
)
def test_the_kept_note_is_written_in_the_language_of_the_message(query: str, language: str) -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = ["OK."]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_kept=("a row",))
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    head = KEPT_NOTE if language == "en" else KEPT_NOTES[language]
    assert "".join(parts) == f"OK.{head}\n- a row)"
    assert kept_note(("a row",), language) == f"{head}\n- a row)"
