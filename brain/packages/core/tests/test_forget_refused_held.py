from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import TickingClock

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
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
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTES
from cortex_core.forget_refused_held import (
    REFUSED_HELD_NOTE,
    REFUSED_HELD_NOTES,
    hold_refused_value,
)
from cortex_core.forget_unrequested import FORGET_UNREQUESTED_MSG
from cortex_core.forget_unsaid import FORGET_UNSAID_MSG
from cortex_core.memory_old_value import old_value_note

_SEED = "User: Merk dir, dass mein Code 5528 ist.\nAssistant: Notiert."
_MESSAGE = "Merk dir, dass der Code ungültig ist."
_REPLY = "Ich habe notiert, dass der Code ungültig ist."


class _Backend:
    def __init__(self, reply: str, calls: Sequence[ToolCall]) -> None:
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
    async def find_value(
        self, value: str, *, limit: int, scopes: Sequence[str] | None = None
    ) -> Sequence[MemoryRecord]:
        del value, limit, scopes
        msg = "pgvector is down"
        raise MemoryStoreError(msg)


def _call(text: str, index: int = 1) -> ToolCall:
    return ToolCall(id=f"c{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _seeded(*texts: str, store: InMemoryMemoryStore | None = None) -> InMemoryMemoryStore:
    store = InMemoryMemoryStore() if store is None else store
    for index, text in enumerate(texts):
        embedding = tuple(await HashEmbedder().embed(text))
        at = datetime(2026, 11, 26, tzinfo=UTC)
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=at))
    return store


async def _turn(
    query: str,
    reply: str,
    calls: Sequence[ToolCall],
    store: InMemoryMemoryStore | None,
) -> tuple[list[str], list[str], str]:
    ran: list[str] = []

    async def forget(arguments: Mapping[str, object]) -> str:
        del arguments
        ran.append(FORGET_CHOSEN_TOOL_NAME)
        return "done"

    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    audit = RecordingAuditSink()
    tools = ToolDispatcher(
        InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, forget)}), audit, TickingClock()
    )
    memory = None if store is None else MemoryRecaller(store, HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=memory, tools=tools)
    engine = TurnEngine(
        InMemorySessionStore(), _Backend(reply, calls), TickingClock(), capabilities=caps
    )
    turn = engine.handle_turn("s", query, turn_id="t")
    shown = "".join([event.text async for event in turn if isinstance(event, TextDelta)])
    return ran, [record.detail for record in audit.records], shown


@pytest.mark.parametrize("named", ["5528", "Code 5528", "55 28", "code: 5528"])
async def test_a_refused_call_naming_a_stored_value_closes_the_reply_with_the_note(
    named: str,
) -> None:
    store = await _seeded(_SEED)
    ran, details, shown = await _turn(_MESSAGE, _REPLY, [_call(named)], store)
    assert (ran, details) == ([], [FORGET_UNREQUESTED_MSG])
    assert shown == _REPLY + REFUSED_HELD_NOTES["de"]
    assert [record.text for record in await store.find_value("5528", limit=5)] == [_SEED]


@pytest.mark.parametrize(
    ("query", "reply", "language"),
    [
        ("Retiens que le code de la porte est périmé.", "J'ai noté que le code est périmé.", "fr"),
        ("Recuerda que el código está caducado.", "He anotado que el código caducó.", "es"),
        ("Ține minte că parola e invalidă.", "Am notat că parola e invalidă.", "ro"),
    ],
)
async def test_the_note_is_written_in_the_language_of_the_message(
    *, query: str, reply: str, language: str
) -> None:
    store = await _seeded("User: Mon code est 5528.\nAssistant: Noté.")
    _ran, _details, shown = await _turn(query, reply, [_call("5528")], store)
    assert shown == reply + REFUSED_HELD_NOTES[language]


@pytest.mark.parametrize(
    ("named", "noted"),
    [("5528", True), ("ancien code 5528", True), ("ancien code", False), ("4417", False)],
)
async def test_a_call_naming_words_a_request_to_remember_lacks_gets_the_note_on_a_held_value(
    *, named: str, noted: bool
) -> None:
    store = await _seeded("User: Retiens que mon code est 5528.\nAssistant: C'est noté.")
    query, reply = "Retiens que ce numéro est faux.", "C'est noté, ce numéro est faux."
    ran, details, shown = await _turn(query, reply, [_call(named)], store)
    assert (ran, details) == ([], [FORGET_UNSAID_MSG])
    assert shown == reply + (REFUSED_HELD_NOTES["fr"] if noted else "")
    assert len(await store.find_value("5528", limit=5)) == 1


async def test_an_english_message_gets_the_english_note() -> None:
    store = await _seeded("User: My locker code is 5528.\nAssistant: Noted.")
    query, reply = "Remember that my locker moved to the second floor.", "Noted."
    _ran, _details, shown = await _turn(query, reply, [_call("5528")], store)
    assert shown == reply + REFUSED_HELD_NOTE


async def test_a_second_refused_call_naming_a_stored_value_shows_the_note_once() -> None:
    store = await _seeded(_SEED)
    calls = [_call("Code", 1), _call("4417", 2), _call("5528", 3), _call("5528", 4)]
    _ran, _details, shown = await _turn(_MESSAGE, _REPLY, calls, store)
    assert shown == _REPLY + REFUSED_HELD_NOTES["de"]


@pytest.mark.parametrize(
    ("named", "rows"),
    [
        ("Code", (_SEED,)),
        ("den alten Code", (_SEED,)),
        ("4417", (_SEED,)),
        ("552", (_SEED,)),
        ("5528", ("User: Merk dir, dass mein Code 155289 ist.\nAssistant: Notiert.",)),
        ("5528", ("User: Merk dir, dass ich am 5.5.28 Geburtstag habe.\nAssistant: Notiert.",)),
        ("5528", ()),
        ("", (_SEED,)),
    ],
)
async def test_a_refused_call_naming_no_stored_value_shows_no_note(
    named: str, rows: tuple[str, ...]
) -> None:
    store = await _seeded(*rows)
    ran, details, shown = await _turn(_MESSAGE, _REPLY, [_call(named)], store)
    assert (ran, details, shown) == ([], [FORGET_UNREQUESTED_MSG], _REPLY)


async def test_a_call_that_ran_shows_no_note() -> None:
    store = await _seeded(_SEED)
    ran, _details, shown = await _turn("Vergiss meinen Code.", "Erledigt.", [_call("5528")], store)
    assert (ran, shown) == ([FORGET_CHOSEN_TOOL_NAME], "Erledigt.")


async def test_a_turn_with_no_memory_shows_no_note() -> None:
    _ran, _details, shown = await _turn(_MESSAGE, _REPLY, [_call("5528")], None)
    assert shown == _REPLY


async def test_a_store_that_cannot_be_read_shows_no_note() -> None:
    store = await _seeded(_SEED, store=_BrokenStore())
    _ran, _details, shown = await _turn(_MESSAGE, _REPLY, [_call("5528")], store)
    assert shown == _REPLY


async def test_a_reply_claiming_a_removal_gets_only_the_note_that_nothing_was_forgotten() -> None:
    store = await _seeded(_SEED)
    reply = "I have removed your old code from my memory."
    _ran, _details, shown = await _turn(_MESSAGE, reply, [_call("5528")], store)
    assert shown == reply + UNFORGOTTEN_CLAIM_NOTES["de"]


async def test_the_note_that_an_old_value_is_still_held_takes_the_place_of_the_note() -> None:
    store = await _seeded(_SEED)
    query, reply = "Merk dir, dass mein Code 4862 ist.", "Ich habe mir deinen Code gemerkt."
    _ran, details, shown = await _turn(query, reply, [_call("5528")], store)
    assert details == [FORGET_UNREQUESTED_MSG]
    assert shown == reply + old_value_note("5528", "de")


def test_the_note_names_no_value() -> None:
    assert all("5528" not in note for note in (REFUSED_HELD_NOTE, *REFUSED_HELD_NOTES.values()))
    assert all("{" not in note for note in (REFUSED_HELD_NOTE, *REFUSED_HELD_NOTES.values()))


async def test_hold_refused_value_reads_only_a_refused_text() -> None:
    store = await _seeded(_SEED)
    caps = TurnCapabilities(memory=MemoryRecaller(store, HashEmbedder(), SystemClock()))
    ran = TaintLedger()
    await hold_refused_value(caps, ran, session_id="s")
    refused = TaintLedger(forget_refused=True, forget_refused_texts=("Code 5528",))
    await hold_refused_value(caps, refused, session_id="s")
    assert (ran.forget_refused_held, refused.forget_refused_held) == (False, True)


async def _never_run(arguments: Mapping[str, object]) -> str:
    raise AssertionError(arguments)


async def _deep(calls: Sequence[ToolCall], taint: TaintLedger | None = None) -> str:
    store = await _seeded(_SEED)
    sessions = InMemorySessionStore()
    at = datetime(2026, 11, 27, tzinfo=UTC)
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_MESSAGE, at=at, turn_id=harness.TURN)
    )
    spec = ToolSpec(name=FORGET_CHOSEN_TOOL_NAME, description="", parameters={})
    registry = InMemoryToolRegistry({FORGET_CHOSEN_TOOL_NAME: (spec, _never_run)})
    tools = ToolDispatcher(registry, RecordingAuditSink(), TickingClock())
    memory = MemoryRecaller(store, HashEmbedder(), SystemClock())
    caps = TurnCapabilities(memory=memory, tools=tools)
    phase = BrainPhase(sessions, _Backend(_REPLY, calls), TickingClock(), "brain", caps)
    record = harness.prepared_slot(taint=taint).snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=at
    )
    return "".join(
        [event.text async for event in phase.run(record) if isinstance(event, TextDelta)]
    )


async def test_a_deep_phase_refused_call_naming_a_stored_value_closes_its_reply_with_the_note() -> (
    None
):
    assert await _deep([_call("5528")]) == _REPLY + REFUSED_HELD_NOTES["de"]


async def test_a_call_the_cortex_had_refused_before_the_handoff_closes_the_deep_reply() -> None:
    cortex = TaintLedger(forget_refused_texts=("Code 5528",))
    assert await _deep([], cortex) == _REPLY + REFUSED_HELD_NOTES["de"]
    assert await _deep([], TaintLedger(forget_refused_texts=("4417",))) == _REPLY
