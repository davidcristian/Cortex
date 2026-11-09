from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    Message,
    RecordingAuditSink,
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
from cortex_core.closing_notes import limit_notes
from cortex_core.conversation import ToolRun
from cortex_core.forget_unfound_claim import (
    DECLINED_FORGET_NOTE,
    DECLINED_FORGET_NOTES,
    declined_note_due,
)
from cortex_core.stops import StopLedger
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest

_AT = datetime(2026, 11, 9, 4, 0, 0, tzinfo=UTC)
_DOOR = "User: Merke dir bitte: Mein Türcode ist 7319.\nAssistant: Notiert."
_ASKED = "Vergiss meinen Türcode, aber behalte die Postleitzahl."
_NEVER = (
    'Ich habe keinen "Türcode" in meinen Erinnerungen gespeichert, daher musste ich nichts löschen.'
)


@pytest.mark.parametrize(
    "reply",
    [
        _NEVER,
        "I don't have a door code stored, so there was nothing to delete.",
        "OK, I won't forget it.",
        "",
    ],
)
def test_a_reply_after_a_declined_card_is_read(reply: str) -> None:
    assert declined_note_due(reply, declined=True)
    assert not declined_note_due(reply, declined=False)


@pytest.mark.parametrize(
    "reply",
    [
        "OK, your door code is still stored.",
        "I've kept it, and I still remember 7319.",
    ],
)
def test_a_reply_saying_the_fact_is_still_held_is_not_read(reply: str) -> None:
    assert not declined_note_due(reply, declined=True)


def _closed(reply: str, query: str, *, declined: bool) -> str:
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_declined=declined)
    caps = TurnCapabilities()
    runs = (ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=not declined),)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("query", "note"),
    [
        ("Forget my door code.", DECLINED_FORGET_NOTE),
        ("Oublie mon code de porte.", DECLINED_FORGET_NOTES["fr"]),
        (_ASKED, DECLINED_FORGET_NOTES["de"]),
        ("Olvida mi código de la puerta, por favor.", DECLINED_FORGET_NOTES["es"]),
        ("Uită codul meu de la ușă.", DECLINED_FORGET_NOTES["ro"]),
    ],
)
def test_the_note_is_written_in_the_message_language(query: str, note: str) -> None:
    assert _closed("OK.", query, declined=True) == "OK." + note


def test_a_failed_forget_that_was_not_declined_closes_with_no_declined_note() -> None:
    assert _closed("OK.", "Forget my door code.", declined=False) == "OK."


class _Rounds:
    def __init__(self, calls: Sequence[ToolCall], reply: str) -> None:
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
        if not self._calls:
            yield TextChunk(self._reply)
            return
        yield self._calls.pop(0)


class _Answer:
    def __init__(self, answer: ConfirmAnswer) -> None:
        self._answer = answer

    async def confirm(self, request: ConfirmationRequest) -> ConfirmAnswer:
        del request
        return self._answer


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(minutes=10, seconds=self._ticks)


async def _turn(answer: ConfirmAnswer, reply: str) -> tuple[str, int]:
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    await store.add(
        MemoryRecord(id="m0", text=_DOOR, embedding=tuple(await embedder.embed(_DOOR)), at=_AT)
    )
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=_Answer(answer),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    caps = TurnCapabilities(memory=MemoryRecaller(store, embedder, SystemClock()), tools=dispatcher)
    call = ToolCall(id="f0", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "Türcode"})
    engine = TurnEngine(InMemorySessionStore(), _Rounds([call], reply), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", _ASKED, turn_id="t-1")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    return shown, await store.count_candidates()


async def test_a_denied_card_closes_a_never_stored_reply_with_the_note() -> None:
    shown, left = await _turn(ConfirmAnswer.DECLINED, _NEVER)
    assert left == 1
    assert shown.endswith(_NEVER + DECLINED_FORGET_NOTES["de"])


async def test_an_approved_card_gets_no_declined_note() -> None:
    shown, left = await _turn(ConfirmAnswer.APPROVED, "Erledigt, der Code ist gelöscht.")
    assert left == 0
    assert DECLINED_FORGET_NOTES["de"] not in shown


async def test_a_card_left_unanswered_gets_no_declined_note() -> None:
    shown, left = await _turn(ConfirmAnswer.EXPIRED, "Die Anfrage ist abgelaufen.")
    assert left == 1
    assert DECLINED_FORGET_NOTES["de"] not in shown
