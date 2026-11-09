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
from cortex_core.forget_unfound_claim import DELETED_UNFOUND_NOTE, says_not_stored, unfound_claim
from cortex_core.stops import StopLedger
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest

_AT = datetime(2026, 11, 8, 4, 0, 0, tzinfo=UTC)
_LOCKER = "User: Remember that my gym locker code is 5819.\nAssistant: Noted."
_PHONE = "User: Remember that my phone number is 0612345678.\nAssistant: Noted."
_PPH2 = "I couldn't find a phone number or passport number in my memory to remove."

_LK3 = (
    "I've removed the code from my memory. It appears I didn't have any specific \"locker "
    "combination\" entries saved, but I've ensured that information is cleared."
)
_RUN = ToolRun(FORGET_CHOSEN_TOOL_NAME, ok=True)

NOT_STORED = [
    _LK3,
    "I didn't find any record of your passport number in my memory.",
    "I couldn't find a phone number or passport number in my memory to remove.",
    "Your bike code was never stored.",
    "The locker combination wasn't saved.",
    "That was not found in my memory.",
    "I couldn\u2019t find your passport number.",
    "I've deleted the code; the locker combination is not stored in my memory.",
    "I've removed the code, but there were no records of the locker combination.",
    "There were no other records of that found to remove.",
    "I have no other record of your passport number stored.",
    "There are no records of it, so nothing else was removed.",
    "No records of the locker combination were found left in my memory.",
]

NEW_NOT_KEPT = [
    "I've deleted your old phone number from my memory. However, your new phone number was not "
    "kept because it was part of a request to forget information. Please send your new phone "
    "number in a separate message so that I can note it for you.",
    "I've forgotten your old phone number. However, because you asked to forget something, your "
    "new phone number was not saved. Please send it again in a new message so I can note it for "
    "you.",
    "I've forgotten your old phone number. However, since this message also included a request to "
    "forget something, your new phone number wasn't saved. Please send it to me in a new message "
    "so I can remember it for you.",
    "I've forgotten your old phone number. However, since your message included a request to "
    "forget something, your new phone number wasn't saved. Please send your new phone number in a "
    "separate message so I can remember it.",
]

NEAR_MISSES = [
    *NEW_NOT_KEPT,
    "I've removed the code from my memory.",
    "I've deleted both the code and the locker combination from my memory.",
    "OK. I've forgotten that information, and nothing else is needed.",
    "Is there anything else you want me to forget?",
    "Do you want me to check whether anything else was not saved?",
    "I've cleared that from my memory, so it is no longer stored.",
    "I've removed the code, so it is not stored in my memory anymore.",
    "I found and deleted it, so you didn't have to wait.",
    "I've deleted the code, and no other records of it remain.",
    "I've forgotten it, and no records of it are kept now.",
    "I've removed it, so no record of it is left in my memory.",
    "I've deleted the code; no other records of it exist any more.",
]


@pytest.mark.parametrize("reply", NOT_STORED)
def test_a_reply_saying_something_was_not_stored_is_read(reply: str) -> None:
    assert says_not_stored(reply)


@pytest.mark.parametrize("reply", NEAR_MISSES)
def test_a_reply_naming_only_the_delete_or_a_new_fact_not_kept_is_not_read(reply: str) -> None:
    assert not says_not_stored(reply)


def test_the_note_needs_a_delete_and_a_call_that_matched_nothing() -> None:
    assert unfound_claim((_RUN, _RUN), _LK3, unmatched=1)
    assert not unfound_claim((_RUN, _RUN), _LK3, unmatched=0)
    assert not unfound_claim((_RUN,), _LK3, unmatched=1)
    assert not unfound_claim((_RUN, _RUN), "I've removed the code.", unmatched=1)


def _closed(reply: str, runs: tuple[ToolRun, ...], unmatched: int) -> str:
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=len(runs), forget_unmatched=unmatched)
    caps = TurnCapabilities()
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query="Forget it."))
    return "".join(parts)


@pytest.mark.parametrize("reply", NOT_STORED)
def test_a_not_stored_reply_after_a_delete_and_a_miss_ends_with_the_note(reply: str) -> None:
    assert _closed(reply, (_RUN, _RUN), 1) == reply + DELETED_UNFOUND_NOTE


@pytest.mark.parametrize("reply", NEW_NOT_KEPT)
def test_a_new_fact_not_kept_after_a_delete_and_a_miss_gets_no_note(reply: str) -> None:
    assert _closed(reply, (_RUN, _RUN), 1) == reply


def test_a_not_stored_reply_on_a_turn_that_deleted_nothing_gets_no_note() -> None:
    reply = "I didn't have that phone number stored in my memory, so there's nothing to forget."
    assert DELETED_UNFOUND_NOTE not in _closed(reply, (_RUN,), 1)
    assert _closed(reply, (_RUN, _RUN), 0) == reply


class _Rounds:
    def __init__(self, rounds: Sequence[Sequence[ToolCall]], reply: str) -> None:
        self._rounds = list(rounds)
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
        if not self._rounds:
            yield TextChunk(self._reply)
            return
        for call in self._rounds.pop(0):
            yield call


class _Approve:
    async def confirm(self, request: ConfirmationRequest) -> ConfirmAnswer:
        del request
        return ConfirmAnswer.APPROVED


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(minutes=10, seconds=self._ticks)


def _forget(text: str, index: int) -> list[ToolCall]:
    return [ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})]


async def _turn(row: str, texts: Sequence[str], reply: str) -> str:
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    await store.add(
        MemoryRecord(id="m0", text=row, embedding=tuple(await embedder.embed(row)), at=_AT)
    )
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=_Approve(),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    caps = TurnCapabilities(memory=MemoryRecaller(store, embedder, SystemClock()), tools=dispatcher)
    rounds = [_forget(text, index) for index, text in enumerate(texts)]
    engine = TurnEngine(InMemorySessionStore(), _Rounds(rounds, reply), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", "Forget it.", turn_id="t-1")]
    return "".join(event.text for event in events if isinstance(event, TextDelta))


@pytest.mark.parametrize(
    ("row", "texts", "reply"),
    [
        (_LOCKER, ("5819", "locker combination"), _LK3),
        (_PHONE, ("0612345678", "passport number"), _PPH2),
    ],
    ids=["same-fact-other-words", "fact-never-stored"],
)
async def test_a_turn_deleting_a_row_then_missing_closes_a_not_stored_reply_with_the_note(
    row: str, texts: tuple[str, str], reply: str
) -> None:
    assert (await _turn(row, texts, reply)).endswith(reply + DELETED_UNFOUND_NOTE)


async def test_a_later_call_that_names_the_delete_gets_no_note() -> None:
    shown = await _turn(_LOCKER, ("5819", "gym locker code"), _LK3)
    assert DELETED_UNFOUND_NOTE not in shown
