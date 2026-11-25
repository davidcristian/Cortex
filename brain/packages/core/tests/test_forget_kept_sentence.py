from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_UNTRUSTED_TOOL_NAME,
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
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_kept_sentence import KEPT_CLAIM_NOTE, KEPT_CLAIM_NOTES, false_sentence
from cortex_core.forget_unnamed import KEPT_NOTE, KEPT_NOTES
from cortex_core.reply_notes import model_text
from cortex_core.stops import StopLedger
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest, TurnStamp

_PHONE = (
    "User: Remember that my phone is 0721 555 4242. Assistant: I've noted that your phone number "
    "is 0721 555 4242."
)
_LOCKER = "User: Remember that my locker code is 4242.\nAssistant: I've noted your locker code."
_HOME = "User: Remember my home phone is 0744 111 2222.\nAssistant: Noted your home phone."
_DOOR = "User: My door code is 1234. Assistant: I've noted your door code, 1234."
_CARD = (
    "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: I've noted your card "
    "number: 4111 1111 1111 4242."
)
_DELETED = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True)
_KEPT_ALL = ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=False)

SAYS_A_KEPT_ROW_WAS_FORGOTTEN = [
    "I've removed the phone number and the locker code from my memory, but I've kept your card.",
    "I have forgotten the phone number as you requested.",
    "The memory regarding the phone number has been removed.",
    "Your phone number has been removed.",
    "I've updated my memory to remove the phone number, while keeping the card.",
    "Done. I've deleted 0721 555 4242.",
    "I\u2019ve removed your phone number.",
    "I've removed your locker code and phone number.",
    "I've deleted the locker code and phone too.",
    "I've deleted the locker and 0721 555 4242.",
    "I've deleted the old entry and locker and phone.",
]
KEPT_ROW_OUTSIDE_THE_REMOVED_OBJECT = [
    "I've removed your locker code and left your card and phone untouched.",
    "I've deleted your locker code and saved your card.",
    "Your locker code has been removed and your phone number was preserved.",
    "I've removed the locker code from the things linked to your card.",
    'I\'ve deleted the locker code you mentioned in "Forget the locker 4242 including the phone."',
    "I've wiped the locker code and moved your card details to the top.",
    "The locker code was deleted and your phone number was left alone.",
    "I've removed the locker code from the note about your phone.",
    "I've removed the entry your message called \u201clocker 4242 near the phone\u201d.",
    "I've deleted the locker code that was linked to your card.",
    "Your phone stays and the locker code has been removed.",
]
REMOVAL_OR_KEPT_ROW_AFTER_A_JOINING_WORD = [
    "I've removed the locker code and phone number from my memory.",
    "I've removed the locker code and phone number in memory stays.",
    "I've removed the locker code and card number of yours is still saved.",
    "I've deleted the locker code and card number and phone number are kept.",
    "I've deleted the locker code and card number and phone number stay.",
    "I've removed the locker code and phone number, as you asked, stays.",
    "I've removed the locker code and phone number, still saved.",
    "I've removed the locker code and phone number (kept).",
    "I've deleted the locker and 0721 555 4242, as you asked.",
    "I've removed the locker code and.",
    "I've deleted your locker code and phone stays.",
    "I've deleted your locker code and phone is kept.",
    "I've deleted your locker code and phone remains saved.",
    "I've removed the locker code and phone number is still in memory.",
    "I've removed the locker code and noted your phone.",
    "I've removed the locker code and phone untouched.",
    "I've removed the locker code and the phone",
    "I have forgotten the locker code and the phone number as you requested.",
    "The memory regarding the locker and the phone number has been removed.",
    "The locker code and your card were deleted.",
    "Your phone number and the locker code have been removed.",
]
TRUE_OR_UNSTATED = [
    "I've removed your locker code from my memory. Your card number (ending 4242) remains saved.",
    "I've removed the locker code. I couldn't remove the phone number as requested.",
    "I've removed the locker code and not the phone number.",
    "I've removed the locker code but kept your phone number.",
    "I've removed the locker code, and your phone number is still in memory.",
    "Your phone number remains and the locker code has been removed.",
    "I've tried to remove the locker code and phone number.",
    "Should I say the phone number was deleted?",
    "Nothing about your phone number was removed.",
    "If I have removed the phone number, ask me again.",
    "I have processed your request to remove the phone number.",
    "J'ai supprimé le numéro de téléphone.",
    "I've deleted that information from my memory.",
    "I couldn\u2019t say your phone number was removed.",
]


@pytest.mark.parametrize("reply", SAYS_A_KEPT_ROW_WAS_FORGOTTEN)
def test_a_statement_naming_a_kept_row_as_forgotten_is_found(reply: str) -> None:
    found = false_sentence(reply, (_PHONE,), (_LOCKER,))
    assert found is not None
    assert found in reply
    assert found.endswith(".")


@pytest.mark.parametrize("reply", TRUE_OR_UNSTATED)
def test_a_true_or_unread_statement_is_not_found(reply: str) -> None:
    assert false_sentence(reply, (_PHONE,), (_LOCKER,)) is None


@pytest.mark.parametrize("reply", KEPT_ROW_OUTSIDE_THE_REMOVED_OBJECT)
def test_a_kept_row_the_removal_does_not_name_as_its_object_is_not_found(reply: str) -> None:
    assert false_sentence(reply, (_CARD, _PHONE), (_LOCKER,)) is None


@pytest.mark.parametrize("reply", REMOVAL_OR_KEPT_ROW_AFTER_A_JOINING_WORD)
def test_a_removal_or_kept_row_after_a_joining_word_is_not_read(reply: str) -> None:
    assert false_sentence(reply, (_CARD, _PHONE), (_LOCKER,)) is None


def test_only_the_sentence_naming_the_kept_row_is_found() -> None:
    reply = "I've removed the locker code. I've also removed your phone number."
    assert false_sentence(reply, (_PHONE,), (_LOCKER,)) == "I've also removed your phone number."


def test_a_word_a_deleted_row_also_holds_names_no_kept_row() -> None:
    reply = "I've removed your home phone number from my memory."
    assert false_sentence(reply, (_PHONE,), (_HOME,)) is None
    assert false_sentence("I've removed your locker code.", (_DOOR,), (_LOCKER,)) is None


def test_a_kept_row_whose_two_sides_share_no_word_is_named_by_its_value_only() -> None:
    row = "User: Remember my phone 0721 555 4242. Assistant: Noted."
    assert false_sentence("I've removed your phone.", (row,), ()) is None
    assert false_sentence("I've removed 0721 555 4242.", (row,), ()) is not None


def _closed(
    reply: str,
    runs: tuple[ToolRun, ...],
    taint: TaintLedger,
    query: str = "Forget the locker 4242 including the phone.",
) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


_SAID = "I've removed the phone number and the locker code from my memory."


def test_the_kept_note_names_the_false_sentence_in_place_of_its_plain_head() -> None:
    taint = TaintLedger(forget_kept=(_PHONE,), forget_gone=(_LOCKER,), forget_deleted=1)
    closed = _closed(_SAID, (_DELETED, _KEPT_ALL), taint)
    head = KEPT_CLAIM_NOTE.lstrip("\n").format(sentence=_SAID)
    assert closed == f"{_SAID}\n\n{head}\n- {_PHONE})"
    assert KEPT_NOTE.strip() not in closed
    assert model_text(closed).rstrip() == _SAID


def test_the_kept_note_keeps_its_plain_head_when_a_deleted_row_is_not_known() -> None:
    plain = KEPT_NOTE.strip()
    unknown = TaintLedger(forget_kept=(_PHONE,), forget_deleted=1)
    assert plain in _closed(_SAID, (_DELETED, _KEPT_ALL), unknown)
    untrusted = ToolRun(name=FORGET_UNTRUSTED_TOOL_NAME, ok=True)
    known = TaintLedger(forget_kept=(_PHONE,), forget_gone=(_LOCKER,), forget_deleted=1)
    assert plain in _closed(_SAID, (_DELETED, untrusted), known)
    assert plain in _closed("I've removed the locker code.", (_DELETED,), known)


def test_the_marked_head_is_in_the_message_language() -> None:
    taint = TaintLedger(forget_kept=(_PHONE,), forget_gone=(_LOCKER,), forget_deleted=1)
    closed = _closed(_SAID, (_DELETED,), taint, query="Oublie le casier 4242 et le téléphone.")
    assert KEPT_CLAIM_NOTES["fr"].strip().format(sentence=_SAID) in closed
    assert KEPT_NOTES["fr"].strip() not in closed


async def test_a_delete_reports_the_text_of_each_row_it_removed() -> None:
    store = InMemoryMemoryStore()
    at = datetime(2026, 11, 24, tzinfo=UTC)
    await store.add(MemoryRecord(id="locker", text=_LOCKER, embedding=(1.0, 0.0), at=at))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query="Forget my locker code.")
    call = ToolCall(
        id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": "locker"}, stamp=stamp
    )
    await tool.card(call)
    result = await tool.invoke(call)
    assert (result.forgot, result.gone) == (1, (_LOCKER,))


class _Calls:
    def __init__(self, reply: str, *texts: str) -> None:
        self._calls = [
            ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})
            for index, text in reversed(list(enumerate(texts)))
        ]
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
        yield self._calls.pop()


class _Approve:
    async def confirm(self, request: ConfirmationRequest) -> ConfirmAnswer:
        del request
        return ConfirmAnswer.APPROVED


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 11, 24, 1, tzinfo=UTC)


async def test_a_turn_whose_delete_kept_a_row_its_reply_says_was_forgotten_marks_that_reply() -> (
    None
):
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    phone = _PHONE.replace(" Assistant: ", "\nAssistant: ")
    for index, row in enumerate((_LOCKER, phone)):
        vector = tuple(await embedder.embed(row))
        at = datetime(2026, 11, 23, index, tzinfo=UTC)
        await store.add(MemoryRecord(id=f"row{index}", text=row, embedding=vector, at=at))
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    policy = DispatchPolicy(
        record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
    )
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=_Approve(),
        policy=policy,
    )
    caps = TurnCapabilities(memory=MemoryRecaller(store, embedder, SystemClock()), tools=dispatcher)
    engine = TurnEngine(
        InMemorySessionStore(), _Calls(_SAID, "4242", "phone"), _Clock(), capabilities=caps
    )
    query = "Forget the locker 4242 including the phone."
    events = [event async for event in engine.handle_turn("s", query, turn_id="t")]
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert [
        hit.record.id for hit in await store.search(tuple(await embedder.embed(phone)), k=5)
    ] == ["row1"]
    assert KEPT_CLAIM_NOTE.strip().format(sentence=_SAID) in shown
    assert KEPT_NOTE.strip() not in shown
