from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    UNFORGOTTEN_CLAIM_NOTE,
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
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.forget_inside import INSIDE_ALL, INSIDE_NOTE, inside_note
from cortex_core.forget_longer import LONGER_ALL, LONGER_NOTE, longer_note
from cortex_core.forget_unfound_claim import UNMATCHED_FORGET_NOTE
from cortex_core.forget_unnamed import KEPT_ALL, kept_note
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest, ToolResult, TurnStamp

_AT = datetime(2026, 11, 10, 3, 0, 0, tzinfo=UTC)
_ACCOUNT = "User: Remember that my phone account is 015 123 456 7890.\nAssistant: Noted."
_SHOWN = "User: Remember that my phone account is 015 123 456 7890. Assistant: Noted."
_FAX = "User: Remember that my fax is 015 123 456 78901.\nAssistant: Noted."
_VALUE = "015 123 456 789"
_LONGER = "015 123 456 7890"
_ASKED = f"Forget {_VALUE}."
_NAMING = f"Forget my phone {_VALUE}."
_WHOLE = f"Forget my phone account {_LONGER}."


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=minutes)
    )


async def _tool(*rows: MemoryRecord) -> ForgetChosenTool:
    store = InMemoryMemoryStore()
    for row in rows:
        await store.add(row)
    return ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)


async def _run(tool: ForgetChosenTool, text: str, query: str, number: int = 0) -> ToolResult:
    stamp = TurnStamp(turn_id="t", query=query)
    call = ToolCall(
        id=f"c{number}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp
    )
    await tool.card(call)
    return await tool.invoke(call)


def test_the_note_names_each_row_and_closes_its_bracket() -> None:
    assert inside_note(["one", "two"]) == f"{INSIDE_NOTE}\n- one\n- two)"
    assert "forget" not in INSIDE_NOTE.split("searched for", 1)[1]


async def test_a_forget_matching_only_inside_a_longer_value_names_that_row() -> None:
    result = await _run(await _tool(_record("account", _ACCOUNT)), _VALUE, _ASKED)
    assert result.content == f"{INSIDE_ALL}."
    assert (result.kept, result.inside) == ((), (_SHOWN,))


async def test_a_forget_keeping_a_row_unnamed_also_names_its_inside_row() -> None:
    tool = await _tool(_record("account", _ACCOUNT), _record("fax", _FAX, 1))
    result = await _run(tool, _LONGER, _ASKED)
    assert result.content == f"{KEPT_ALL}."
    fax = "User: Remember that my fax is 015 123 456 78901. Assistant: Noted."
    assert (result.kept, result.inside) == ((_SHOWN,), (fax,))


async def test_a_row_listed_on_a_card_beside_an_inside_row_is_not_named_by_the_note() -> None:
    phone = _record("phone", "User: My phone is 015 123 456 789, remember it.\nAssistant: Noted.")
    result = await _run(await _tool(phone, _record("account", _ACCOUNT, 1)), _VALUE, _ASKED)
    assert result.forgot == 1
    assert result.inside == ()


async def test_a_row_a_later_call_keeps_unnamed_is_named_once_by_the_kept_note() -> None:
    tool = await _tool(_record("account", _ACCOUNT))
    first = await _run(tool, _VALUE, _ASKED)
    later = await _run(tool, _LONGER, _ASKED, 1)
    assert first.inside == (_SHOWN,)
    assert (later.kept, later.inside) == ((_SHOWN,), ())


async def test_a_row_an_earlier_call_kept_unnamed_is_not_named_again() -> None:
    tool = await _tool(_record("account", _ACCOUNT))
    first = await _run(tool, _LONGER, _ASKED)
    later = await _run(tool, _VALUE, _ASKED, 1)
    assert first.kept == (_SHOWN,)
    assert (later.kept, later.inside) == ((_SHOWN,), ())


async def test_a_row_a_later_card_deletes_leaves_the_note() -> None:
    tool = await _tool(_record("account", _ACCOUNT))
    first = await _run(tool, _VALUE, _WHOLE)
    later = await _run(tool, _LONGER, _WHOLE, 1)
    assert first.inside == (_SHOWN,)
    assert (later.forgot, later.inside) == (1, ())


class _Rounds:
    def __init__(self, texts: Sequence[str], reply: str) -> None:
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
        return _AT + timedelta(minutes=10)


async def _turn(
    texts: Sequence[str], reply: str, query: str = _ASKED, rows: Sequence[str] = (_ACCOUNT,)
) -> str:
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    for index, row in enumerate(rows):
        vector = tuple(await embedder.embed(row))
        record_id = "account" if index == 0 else f"row{index}"
        await store.add(MemoryRecord(id=record_id, text=row, embedding=vector, at=_AT))
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
    engine = TurnEngine(InMemorySessionStore(), _Rounds(texts, reply), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", query, turn_id="t")]
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_a_turn_whose_forget_kept_only_a_longer_value_closes_naming_that_row() -> None:
    reply = "Nothing was deleted: the number stored is a longer, different one."
    assert await _turn([_VALUE], reply) == reply + inside_note([_SHOWN])


async def test_a_forgotten_claim_after_such_a_forget_gets_both_notes_in_order() -> None:
    shown = await _turn([_VALUE], "I've forgotten that number.")
    assert shown == "I've forgotten that number." + UNFORGOTTEN_CLAIM_NOTE + inside_note([_SHOWN])


async def test_a_turn_also_calling_a_value_never_stored_gets_both_notes() -> None:
    shown = await _turn([_VALUE, "0170 5555"], "Nothing matched.")
    assert shown == "Nothing matched." + inside_note([_SHOWN]) + UNMATCHED_FORGET_NOTE


async def test_a_turn_calling_the_longer_value_after_names_the_row_only_as_kept() -> None:
    shown = await _turn([_VALUE, _LONGER], "Nothing was deleted.")
    assert shown == "Nothing was deleted." + kept_note([_SHOWN])


async def test_a_turn_deleting_the_row_by_a_later_card_shows_no_inside_note() -> None:
    shown = await _turn([_VALUE, _LONGER], "Deleted it.", _WHOLE)
    assert INSIDE_NOTE not in shown


async def test_a_turn_calling_a_longer_value_than_the_message_names_keeps_the_row() -> None:
    shown = await _turn([_LONGER], "I've forgotten that number.", _NAMING)
    reply = "I've forgotten that number."
    assert shown == reply + UNFORGOTTEN_CLAIM_NOTE + longer_note([_SHOWN])


async def test_a_turn_keeping_a_row_for_the_message_value_inside_a_longer_one_names_it() -> None:
    shown = await _turn([_LONGER], "Nothing was deleted.", _NAMING)
    assert shown == "Nothing was deleted." + longer_note([_SHOWN])


async def test_a_turn_deleting_that_row_by_a_later_card_shows_no_longer_note() -> None:
    shown = await _turn([_LONGER, "phone"], "Deleted it.", _NAMING)
    assert LONGER_NOTE not in shown


async def test_a_row_kept_for_both_reasons_is_named_once_by_the_longer_note() -> None:
    shown = await _turn([_VALUE, _LONGER], "Nothing was deleted.", _NAMING)
    assert shown == "Nothing was deleted." + longer_note([_SHOWN])


async def test_a_turn_keeping_both_kinds_of_row_names_each_once_in_its_own_note() -> None:
    shown = await _turn([_LONGER], "Nothing was deleted.", _NAMING, (_ACCOUNT, _FAX))
    fax = " ".join(_FAX.split())
    assert shown == "Nothing was deleted." + inside_note([fax]) + longer_note([_SHOWN])


async def test_a_forget_keeping_a_row_for_the_message_value_names_it_until_deleted() -> None:
    tool = await _tool(_record("account", _ACCOUNT))
    first = await _run(tool, _LONGER, _NAMING)
    later = await _run(tool, "phone", _NAMING, 1)
    assert (first.content, first.longer, first.inside) == (f"{LONGER_ALL}.", (_SHOWN,), ())
    assert (later.forgot, later.longer) == (1, ())
