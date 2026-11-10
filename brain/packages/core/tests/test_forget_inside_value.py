from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

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
from cortex_core.forget_inside import INSIDE_ALL, INSIDE_LINE, inside
from cortex_core.forget_unfound_claim import UNMATCHED_FORGET_NOTE
from cortex_core.forget_unnamed import kept_note
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest

_AT = datetime(2026, 11, 10, 3, 0, 0, tzinfo=UTC)
_PHONE = "User: My phone is 015 123 456 789, remember it.\nAssistant: Noted."
_ACCOUNT = "User: Remember that my phone account is 015 123 456 7890.\nAssistant: Noted."
_CARD = "User: Remember my card number 4242 4242 4242 4242.\nAssistant: Noted."
_VALUE = "015 123 456 789"


def _record(record_id: str, text: str, minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=text, embedding=(1.0, 0.0), at=_AT + timedelta(minutes=minutes)
    )


def _call(text: str) -> ToolCall:
    return ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _forget(text: str, *rows: MemoryRecord) -> tuple[list[str] | None, str, list[str]]:
    store = InMemoryMemoryStore()
    for row in rows:
        await store.add(row)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    card = await tool.card(_call(text))
    result = await tool.invoke(_call(text))
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))
    return (None if card is None else card.splitlines()), result.content, left


async def test_the_value_lists_its_own_row_and_keeps_a_row_holding_a_longer_number() -> None:
    lines, said, left = await _forget(
        _VALUE, _record("phone", _PHONE), _record("account", _ACCOUNT, 1)
    )
    assert lines == [
        "Deletes for good, with no undo, these 1 remembered exchanges:",
        "- User: My phone is 015 123 456 789, remember it. Assistant: Noted.",
        INSIDE_LINE,
        "- User: Remember that my phone account is 015 123 456 7890. Assistant: Noted.",
    ]
    assert said == "forgot 1 remembered exchanges; no remembered exchange contains that text now."
    assert left == ["account"]


@pytest.mark.parametrize(
    "near",
    [
        "User: My phone account is 015 123 456 7890.\nAssistant: Noted.",
        "User: My router code is 015 123 456 789b.\nAssistant: Noted.",
        "User: My fax is 2015 123 456 789.\nAssistant: Noted.",
        "User: The ticket is A015 123 456 789.\nAssistant: Noted.",
    ],
    ids=["longer-number", "longer-code", "leading-digit", "leading-letter"],
)
async def test_a_row_holding_the_value_inside_a_longer_one_stays(near: str) -> None:
    lines, _, left = await _forget(_VALUE, _record("phone", _PHONE), _record("near", near, 1))
    assert lines is not None
    assert lines[2] == INSIDE_LINE
    assert left == ["near"]


@pytest.mark.parametrize(
    "row",
    [
        _CARD,
        "User: My card ends in 4242.\nAssistant: Noted, ending 4242.",
        "User: The card is 4242-4242-4242-4242.\nAssistant: Noted.",
        "User: PIN:4242!\nAssistant: Noted.",
    ],
    ids=["last-group", "alone", "hyphens", "punctuation"],
)
async def test_a_value_named_by_a_whole_group_of_the_row_is_listed_and_deleted(row: str) -> None:
    lines, said, left = await _forget("4242", _record("card", row))
    assert lines is not None
    assert INSIDE_LINE not in lines
    assert said.startswith("forgot 1 remembered exchanges;")
    assert left == []


async def test_a_row_writing_the_value_with_other_separators_is_still_deleted() -> None:
    dashed = "User: My phone is 015-123-456-789.\nAssistant: Noted."
    lines, said, left = await _forget(
        _VALUE, _record("phone", _PHONE), _record("account", _ACCOUNT, 1), _record("d", dashed, 2)
    )
    assert lines == [
        "Deletes for good, with no undo, these 2 remembered exchanges:",
        "- User: My phone is 015 123 456 789, remember it. Assistant: Noted.",
        "Listed because they also hold 015 123 456 789:",
        "- User: My phone is 015-123-456-789. Assistant: Noted.",
        INSIDE_LINE,
        "- User: Remember that my phone account is 015 123 456 7890. Assistant: Noted.",
    ]
    assert said.startswith("forgot 2 remembered exchanges;")
    assert left == ["account"]


async def test_the_value_finds_a_row_with_other_separators_beside_a_longer_number_alone() -> None:
    dashed = "User: My phone is 015-123-456-789.\nAssistant: Noted."
    lines, said, left = await _forget(
        _VALUE, _record("account", _ACCOUNT), _record("dashed", dashed, 1)
    )
    assert lines is not None
    assert lines[1:3] == [
        "Listed because they also hold 015 123 456 789:",
        "- User: My phone is 015-123-456-789. Assistant: Noted.",
    ]
    assert said.startswith("forgot 1 remembered exchanges;")
    assert left == ["account"]


@pytest.mark.parametrize(
    "beside",
    ["my PIN 44 17", "my door code 44-17", "my PIN 4417"],
    ids=["spaces", "hyphen", "glued-elsewhere"],
)
async def test_a_row_also_holding_the_value_whole_is_listed_and_not_shown_kept(beside: str) -> None:
    row = f"User: Remember my account 44170 and {beside}.\nAssistant: Noted."
    lines, said, left = await _forget("4417", _record("both", row))
    assert lines is not None
    assert INSIDE_LINE not in lines
    assert said.startswith("forgot 1 remembered exchanges;")
    assert left == []


@pytest.mark.parametrize(
    "beside", ["my PIN 44 18", "my PIN 4-4-1-7-0"], ids=["other-digits", "longer-in-groups"]
)
async def test_a_row_holding_no_whole_value_named_beside_a_longer_one_stays_kept(
    beside: str,
) -> None:
    row = f"User: Remember my account 44170 and {beside}.\nAssistant: Noted."
    lines, said, left = await _forget("4417", _record("both", row))
    assert lines is None
    assert said == f"{INSIDE_ALL}."
    assert left == ["both"]


async def test_a_value_held_only_inside_a_longer_number_deletes_nothing_and_shows_no_card() -> None:
    store = InMemoryMemoryStore()
    await store.add(_record("account", _ACCOUNT))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    assert await tool.card(_call(_VALUE)) is None
    result = await tool.invoke(_call(_VALUE))
    assert result.content == f"{INSIDE_ALL}."
    assert result.is_error
    assert not result.matched_nothing
    assert result.kept == ()
    assert result.spared == (
        "User: Remember that my phone account is 015 123 456 7890. Assistant: Noted.",
    )
    assert len(await store.find_text(_VALUE, limit=5)) == 1


@pytest.mark.parametrize(
    ("text", "row"),
    [
        ("pass", "User: My passport is in the drawer.\nAssistant: Noted."),
        ("PIN 4417", "User: My PIN 4417 is new.\nAssistant: Noted."),
        ("code 4417", "User: My doorcode 4417 is new.\nAssistant: Noted."),
        ("+49 151", "User: Call +49 151 now.\nAssistant: Noted."),
    ],
    ids=["word", "word-and-value", "word-glued-before", "leading-mark"],
)
def test_a_text_whose_end_holds_no_glued_value_keeps_no_row(text: str, row: str) -> None:
    assert inside([_record("r", row)], text) == frozenset()


def test_a_word_and_value_text_keeps_a_row_holding_a_longer_value() -> None:
    row = "User: My PIN 44170 is new.\nAssistant: Noted."
    assert inside([_record("r", row)], "PIN 4417") == {"r"}


def test_a_value_glued_at_the_start_is_kept_while_the_same_text_elsewhere_is_not() -> None:
    glued = _record("glued", "User: Codes 94417 and 4417x.\nAssistant: Noted.")
    both = _record("both", "User: Codes 94417 and 4417.\nAssistant: Noted.")
    assert inside([glued, both], "4417") == {"glued"}


class _Rounds:
    def __init__(self, text: str, reply: str) -> None:
        self._calls = [ToolCall(id="f0", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})]
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


async def _turn(reply: str) -> str:
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    vector = tuple(await embedder.embed(_ACCOUNT))
    await store.add(MemoryRecord(id="account", text=_ACCOUNT, embedding=vector, at=_AT))
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
    engine = TurnEngine(InMemorySessionStore(), _Rounds(_VALUE, reply), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", f"Forget {_VALUE}.", turn_id="t")]
    assert len(await store.find_text(_VALUE, limit=5)) == 1
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_a_turn_keeping_its_only_match_gets_no_matched_nothing_note() -> None:
    reply = "Nothing was deleted: the number stored is a longer, different one."
    assert await _turn(reply) == reply


async def test_a_turn_keeping_its_only_match_closes_a_forgotten_claim_with_the_note() -> None:
    shown = await _turn("I've forgotten that number.")
    assert shown == "I've forgotten that number." + UNFORGOTTEN_CLAIM_NOTE
    assert UNMATCHED_FORGET_NOTE not in shown
    assert kept_note([_ACCOUNT]) not in shown
