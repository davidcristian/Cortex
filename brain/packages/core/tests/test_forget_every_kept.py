from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
import swap_harness as harness
from swap_harness import TickingClock

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    Message,
    RecordingAuditSink,
    Role,
    SessionMemoryScope,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.closing_notes import limit_notes
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, UNFORGOTTEN_CLAIM_NOTES
from cortex_core.forget_every_kept import (
    EVERY_KEPT_NOTE,
    EVERY_KEPT_NOTES,
    every_kept_due,
    hold_every_kept,
    keeping_form,
)
from cortex_core.forget_refused_held import REFUSED_HELD_NOTE
from cortex_core.forget_uncalled import UNCALLED_FORGET_NOTE, UNCALLED_FORGET_NOTES
from cortex_core.forget_unfound_claim import UNMATCHED_FORGET_NOTE
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.reply_notes import claim_corrected, model_text
from cortex_core.stops import StopLedger
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 27, tzinfo=UTC)
_ROWS = {
    "en": {
        "locker": "User: Remember that my locker code is 4242.\nAssistant: Noted.",
        "card": "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: Noted.",
        "phone": "User: Remember that my phone is 0721 555 4242.\nAssistant: Noted.",
    },
    "fr": {
        "locker": "User: Retiens que le code du casier est 4242.\nAssistant: Noté.",
        "card": "User: Retiens que ma carte est 4111 1111 1111 4242.\nAssistant: Noté.",
        "phone": "User: Retiens que mon téléphone est 0721 555 4242.\nAssistant: Noté.",
    },
    "de": {
        "locker": "User: Merke dir, der Code vom Spind ist 4242.\nAssistant: Notiert.",
        "card": "User: Merke dir, meine Karte ist 4111 1111 1111 4242.\nAssistant: Notiert.",
        "phone": "User: Merke dir, mein Handy ist 0721 555 4242.\nAssistant: Notiert.",
    },
    "es": {
        "locker": "User: Recuerda que el código del gimnasio es 4242.\nAssistant: Anotado.",
        "card": "User: Recuerda que mi tarjeta es 4111 1111 1111 4242.\nAssistant: Anotado.",
        "phone": "User: Recuerda que mi teléfono es 0721 555 4242.\nAssistant: Anotado.",
    },
    "ro": {
        "locker": "User: Ține minte că codul de la dulap este 4242.\nAssistant: Notat.",
        "card": "User: Ține minte că cardul meu este 4111 1111 1111 4242.\nAssistant: Notat.",
        "phone": "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Notat.",
    },
}
_MESSAGES = {
    "en": ("Forget everything, my card stays.", "Forget everything but my card."),
    "fr": ("Oublie tout, ma carte reste.", "Oublie tout sauf ma carte."),
}
_TEXTS = {
    "en": {"locker": "locker", "phone": "phone", "card": "card"},
    "fr": {"locker": "casier", "phone": "téléphone", "card": "carte"},
    "de": {"locker": "Spind", "phone": "Handy", "card": "Karte"},
    "es": {"locker": "gimnasio", "phone": "teléfono", "card": "tarjeta"},
    "ro": {"locker": "dulap", "phone": "telefonul", "card": "cardul"},
}
_LEFT_OUT = {
    "de": "Vergiss alles außer meiner Karte.",
    "es": "Olvida todo excepto mi tarjeta.",
    "ro": "Uită totul în afară de cardul meu.",
}
_CLAIM = "I've forgotten everything except your card."
_PLAIN = "Understood."


class _Backend:
    def __init__(self, reply: str, calls: Sequence[ToolCall] = ()) -> None:
        self._calls = list(calls)
        self._reply = reply

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk(self._reply)


class _BrokenStore(InMemoryMemoryStore):
    async def find_text(
        self, text: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        del text, limit, scopes
        msg = "pgvector is down"
        raise MemoryStoreError(msg)


async def _seeded(language: str, store: InMemoryMemoryStore | None = None) -> InMemoryMemoryStore:
    store = InMemoryMemoryStore() if store is None else store
    for index, (name, text) in enumerate(_ROWS[language].items()):
        at = _AT + timedelta(minutes=index)
        embedding = tuple(await HashEmbedder().embed(text))
        await store.add(MemoryRecord(id=name, text=text, embedding=embedding, at=at))
    return store


async def _ids(store: InMemoryMemoryStore) -> set[str]:
    probe = tuple(await HashEmbedder().embed("memory"))
    return {hit.record.id for hit in await store.search(probe, k=10)}


async def _turn(
    query: str, reply: str, store: InMemoryMemoryStore | None, calls: Sequence[ToolCall] = ()
) -> str:
    async def forget(arguments: Mapping[str, object]) -> ToolResult:
        del arguments
        return ToolResult(call_id="c1", content="forgot 1 remembered exchanges", forgot=1)

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    tools = ToolDispatcher(
        InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)}),
        RecordingAuditSink(),
        TickingClock(),
    )
    memory = None if store is None else MemoryRecaller(store, HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=memory, tools=tools)
    engine = TurnEngine(
        InMemorySessionStore(), _Backend(reply, calls), TickingClock(), capabilities=caps
    )
    turn = engine.handle_turn("s", query, turn_id="t")
    return "".join([event.text async for event in turn if isinstance(event, TextDelta)])


async def _deleted(store: InMemoryMemoryStore, query: str, text: str) -> set[str]:
    before = await _ids(store)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-new", turn_id="t1", query=query)
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)
    await tool.card(call)
    await tool.invoke(call)
    return before - await _ids(store)


@pytest.mark.parametrize("reply", [_CLAIM, _PLAIN])
@pytest.mark.parametrize("language", list(_MESSAGES))
async def test_a_forget_of_everything_keeping_a_row_unread_names_the_form_the_card_reads(
    *, language: str, reply: str
) -> None:
    message, form = _MESSAGES[language]
    note = (EVERY_KEPT_NOTES.get(language) or EVERY_KEPT_NOTE).format(form=form)
    assert await _turn(message, reply, await _seeded(language)) == reply + note


@pytest.mark.parametrize("language", list(_MESSAGES))
async def test_the_form_the_note_names_keeps_the_row_and_lets_each_other_row_be_forgotten(
    language: str,
) -> None:
    form = _MESSAGES[language][1]
    texts = _TEXTS[language]
    assert await _deleted(await _seeded(language), form, texts["card"]) == set()
    assert await _deleted(await _seeded(language), form, texts["locker"]) == {"locker"}
    assert await _deleted(await _seeded(language), form, texts["phone"]) == {"phone"}
    assert await _deleted(await _seeded(language), form, "4242") == {"locker"}


@pytest.mark.parametrize("language", list(_LEFT_OUT))
async def test_a_language_left_out_of_the_note_keeps_every_row_under_its_form(
    language: str,
) -> None:
    for text in (*_TEXTS[language].values(), "4242"):
        assert await _deleted(await _seeded(language), _LEFT_OUT[language], text) == set()


@pytest.mark.parametrize(
    ("message", "words", "form"),
    [
        (
            "Please forget everything, the card stays.",
            {"card"},
            "Please forget everything but the card.",
        ),
        ("Forget everything; card stays.", {"card"}, "Forget everything but card."),
        ("Forget everything, my card and my phone stay.", {"card", "phone"}, ""),
        ("Forget everything, my card stays.", {"phone"}, ""),
        ("Forget everything, row 7 stays.", {"7"}, ""),
        ("Forget everything, mi tarjeta se queda con el código.", {"tarjeta"}, ""),
        ("Forget my card.", {"card"}, ""),
        ("Forget everything, old card stays.", {"card"}, "Forget everything but card."),
        ("Forget everything, my card stays.", {"my"}, ""),
    ],
)
def test_keeping_form_names_only_a_form_the_readers_read_as_keeping_the_one_word(
    *, message: str, words: set[str], form: str
) -> None:
    assert keeping_form(message, words) == form


async def test_two_unread_row_words_give_no_note() -> None:
    message = "Forget everything, my card and phone stay."
    shown = await _turn(message, _PLAIN, await _seeded("en"))
    assert EVERY_KEPT_NOTE.split("{")[0] not in shown


async def test_a_message_naming_no_stored_row_gets_the_note_that_no_call_ran() -> None:
    shown = await _turn("Forget everything, my bike stays.", _PLAIN, await _seeded("en"))
    assert shown == _PLAIN + UNCALLED_FORGET_NOTE


async def test_a_code_word_naming_no_stored_row_gives_no_note() -> None:
    shown = await _turn("Forget everything, my pin stays.", _PLAIN, await _seeded("en"))
    assert shown == _PLAIN + UNCALLED_FORGET_NOTE


async def test_the_recaller_finds_a_text_only_in_the_scopes_the_chat_can_recall() -> None:
    store = InMemoryMemoryStore()
    memory = MemoryRecaller(store, HashEmbedder(), SystemClock(), scope=SessionMemoryScope())
    row = await memory.record(_ROWS["en"]["card"], session_id="chat-a")
    assert row is not None
    found = await memory.find_text("card", session_id="chat-a", limit=5)
    assert [record.id for record in found] == [row.id]
    assert list(await memory.find_text("card", session_id="chat-b", limit=5)) == []


async def test_a_message_that_is_no_forget_of_everything_reads_no_row() -> None:
    taint = TaintLedger()
    memory = MemoryRecaller(_BrokenStore(), HashEmbedder(), SystemClock())
    await hold_every_kept(
        TurnCapabilities(memory=memory), taint, query="Forget my card.", session_id="s"
    )
    assert taint.forget_every_kept == ""


async def test_a_turn_with_no_memory_or_a_store_that_cannot_be_read_gets_the_older_note() -> None:
    message = _MESSAGES["fr"][0]
    assert await _turn(message, _PLAIN, None) == _PLAIN + UNCALLED_FORGET_NOTES["fr"]
    broken = await _seeded("fr", _BrokenStore())
    assert await _turn(message, _CLAIM, broken) == _CLAIM + UNFORGOTTEN_CLAIM_NOTES["fr"]


async def test_a_turn_whose_forget_call_deleted_a_row_gets_no_note() -> None:
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "locker"})
    shown = await _turn(_MESSAGES["en"][0], "Done.", await _seeded("en"), [call])
    assert EVERY_KEPT_NOTE.split("{")[0] not in shown


_FORM = "Forget everything but my card."
_DUE = TaintLedger(forget_every_kept=_FORM)
_OK_FORGET = ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True)


@pytest.mark.parametrize(
    ("taint", "made", "runs", "due"),
    [
        (_DUE, (), (), True),
        (TaintLedger(), (), (), False),
        (TaintLedger(forget_every_kept=_FORM, forget_deleted=1), (), (), False),
        (TaintLedger(forget_every_kept=_FORM, forget_declined=True), (), (), False),
        (TaintLedger(forget_every_kept=_FORM, old_value="4242"), (), (), False),
        (_DUE, (ToolRun(FORGET_UNTRUSTED_TOOL_NAME, ok=True),), (), False),
        (_DUE, (ToolRun(FORGET_UNTRUSTED_TOOL_NAME, ok=False),), (), True),
        (_DUE, (_OK_FORGET,), (), True),
        (_DUE, (), (ToolRun(ESCALATE_TOOL_NAME, ok=True),), False),
    ],
)
def test_the_note_is_due_only_while_nothing_of_the_turn_was_deleted_or_handed_off(
    *, taint: TaintLedger, made: tuple[ToolRun, ...], runs: tuple[ToolRun, ...], due: bool
) -> None:
    assert every_kept_due(taint, made, runs) is due


def _closed(taint: TaintLedger, runs: tuple[ToolRun, ...], reply: str) -> str:
    parts = [reply]
    caps = TurnCapabilities()
    query = _MESSAGES["en"][0]
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("taint", "runs", "reply"),
    [
        (_DUE, (), _CLAIM),
        (_DUE, (), _PLAIN),
        (TaintLedger(forget_every_kept=_FORM, forget_refused_held=True), (), _PLAIN),
        (
            TaintLedger(forget_every_kept=_FORM, forget_calls=1, forget_unmatched=1),
            (_OK_FORGET,),
            _CLAIM,
        ),
    ],
)
def test_the_note_takes_the_place_of_every_note_that_says_nothing_was_deleted(
    *, taint: TaintLedger, runs: tuple[ToolRun, ...], reply: str
) -> None:
    shown = _closed(taint, runs, reply)
    assert shown == reply + EVERY_KEPT_NOTE.format(form=_FORM)
    for older in (UNFORGOTTEN_CLAIM_NOTE, UNCALLED_FORGET_NOTE, REFUSED_HELD_NOTE):
        assert older not in shown
    assert UNMATCHED_FORGET_NOTE not in shown
    assert shown.count("in a message of its own") == 0


def test_the_note_is_left_out_of_a_reply_read_back_and_marks_its_claim_corrected() -> None:
    for note in (EVERY_KEPT_NOTE, *EVERY_KEPT_NOTES.values()):
        assert model_text(_CLAIM + note.format(form=_FORM)).rstrip() == _CLAIM
        assert claim_corrected(_CLAIM + note.format(form=_FORM))


async def test_a_deep_phase_reply_to_a_forget_of_everything_gets_the_note() -> None:
    message, form = _MESSAGES["en"]
    sessions = InMemorySessionStore()
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=message, at=_AT, turn_id=harness.TURN)
    )
    memory = MemoryRecaller(await _seeded("en"), HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=memory)
    phase = BrainPhase(sessions, _Backend(_CLAIM), TickingClock(), "brain", caps)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    shown = "".join(
        [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    )
    assert shown == _CLAIM + EVERY_KEPT_NOTE.format(form=form)
