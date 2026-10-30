from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    FORGET_CHOSEN_LIMIT,
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_NOT_KEPT_NOTE,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    MemoryStoreError,
    SessionMemoryScope,
    ToolCall,
    ToolResult,
    TurnStamp,
)

_AT = datetime(2026, 10, 28, 4, 0, 0, tzinfo=UTC)
_CARD = "User: Remember that my card number is 4242 4242 4242 4242.\nAssistant: Noted."
_RECALL = "User: What do you remember?\nAssistant: Your card number is 4242 4242 4242 4242."


def _record(record_id: str, text: str, *, scope: str = "global", minutes: int = 0) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        text=text,
        embedding=(1.0, 0.0),
        at=_AT + timedelta(minutes=minutes),
        scope=scope,
    )


async def _store(*records: MemoryRecord) -> InMemoryMemoryStore:
    store = InMemoryMemoryStore()
    for record in records:
        await store.add(record)
    return store


async def _texts(store: InMemoryMemoryStore) -> list[str]:
    return sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=100))


def _said(result: ToolResult) -> str:
    assert result.content.endswith(".")
    return result.content.removesuffix(".")


async def _card_lines(tool: ForgetChosenTool, call: ToolCall) -> list[str]:
    card = await tool.card(call)
    assert card is not None
    return card.splitlines()


def _call(text: object = "4242 4242", *, call_id: str = "c1", session: str = "chat-a") -> ToolCall:
    return ToolCall(
        id=call_id,
        name=FORGET_CHOSEN_TOOL_NAME,
        arguments={"text": text},
        stamp=TurnStamp(session_id=session),
    )


class _FailingDelete(InMemoryMemoryStore):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        del ids
        msg = "pgvector is down"
        raise MemoryStoreError(msg)


class _WrittenDuringTheCard(InMemoryMemoryStore):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        removed = await super().delete_ids(ids)
        await self.add(_record("late", "Assistant: it is 4242 4242 4242 4242", minutes=9))
        return removed


def test_the_tool_needs_confirmation_and_one_text() -> None:
    spec = ForgetChosenTool(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE).spec
    assert spec.name == "forget_memories"
    assert spec.confirm_required is True
    assert spec.parameters["required"] == ["text"]


def test_every_result_of_the_tool_is_to_end_with_the_not_kept_note() -> None:
    tool = ForgetChosenTool(InMemoryMemoryStore(), GLOBAL_MEMORY_SCOPE)
    assert tool.result_note == FORGET_NOT_KEPT_NOTE


async def test_the_card_lists_every_matching_memory_and_the_forget_deletes_them() -> None:
    store = await _store(
        _record("card", _CARD), _record("recall", _RECALL, minutes=1), _record("wifi", "wifi")
    )
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    assert await _card_lines(tool, _call()) == [
        "Deletes for good, with no undo, these 2 remembered exchanges:",
        "- User: Remember that my card number is 4242 4242 4242 4242. Assistant: Noted.",
        "- User: What do you remember? Assistant: Your card number is 4242 4242 4242 4242.",
    ]
    result = await tool.invoke(_call())
    assert result.is_error is False
    assert _said(result) == (
        "forgot 2 remembered exchanges; no remembered exchange contains that text now"
    )
    assert await _texts(store) == ["wifi"]


async def test_a_word_naming_the_fact_lists_the_memory_that_holds_its_value() -> None:
    held = "User: My passport number is X1234567.\nAssistant: Noted."
    store = await _store(_record("passport", held), _record("wifi", "wifi"))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    lines = await _card_lines(tool, _call("Passport"))
    assert lines[1] == "- User: My passport number is X1234567. Assistant: Noted."
    assert _said(await tool.invoke(_call("Passport"))).startswith("forgot 1 remembered")
    assert await _texts(store) == ["wifi"]


async def test_a_long_memory_is_cut_around_the_text_on_the_card() -> None:
    text = "x" * 100 + " card 4242 4242 " + "y" * 100
    tool = ForgetChosenTool(await _store(_record("long", text)), GLOBAL_MEMORY_SCOPE)
    line = (await _card_lines(tool, _call()))[1]
    assert line == f"- ...{'x' * 54} card 4242 4242 {'y' * 59}..."


async def test_the_delete_removes_only_what_the_card_showed() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    await tool.card(_call())
    await store.add(_record("later", _RECALL, minutes=5))
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert _said(result) == (
        "forgot 1 remembered exchanges, but 1 written since the card was shown still contain "
        "that text, so it is not forgotten"
    )
    assert await _texts(store) == ["later"]


async def test_a_memory_written_during_the_delete_is_reported_as_left() -> None:
    store = _WrittenDuringTheCard()
    await store.add(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    await tool.card(_call())
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert "but 1 written since the card was shown" in _said(result)


async def test_a_session_scope_reaches_only_what_that_chat_can_recall() -> None:
    store = await _store(_record("mine", _CARD, scope="chat-a"), _record("other", _CARD, scope="b"))
    tool = ForgetChosenTool(store, SessionMemoryScope())
    await tool.card(_call())
    assert _said(await tool.invoke(_call())).startswith("forgot 1 remembered exchanges;")
    assert await _texts(store) == ["other"]


async def test_nothing_matching_says_so_and_deletes_nothing() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    assert await tool.card(_call("passport")) is None
    result = await tool.invoke(_call("passport"))
    assert result.is_error is False
    assert result.matched_nothing is True
    assert _said(result) == (
        "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
        "nothing about it was stored, and do not ask the user for the value"
    )
    assert await _texts(store) == ["card"]


async def test_a_missing_or_blank_text_deletes_nothing() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    for text in ("   ", 4242):
        assert await tool.card(_call(text)) is None
        result = await tool.invoke(_call(text))
        assert result.is_error is True
        assert result.matched_nothing is False
        assert _said(result) == "nothing was forgotten: the call named no text"
    assert await _texts(store) == ["card"]


async def test_more_matches_than_the_card_can_list_deletes_nothing() -> None:
    records = [_record(f"m{i:02}", _CARD, minutes=i) for i in range(FORGET_CHOSEN_LIMIT + 1)]
    store = await _store(*records)
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    assert await tool.card(_call()) is None
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert _said(result).startswith(f"nothing was forgotten: more than {FORGET_CHOSEN_LIMIT}")
    assert len(await _texts(store)) == FORGET_CHOSEN_LIMIT + 1


async def test_exactly_the_limit_is_listed_and_deleted() -> None:
    records = [_record(f"m{i:02}", _CARD, minutes=i) for i in range(FORGET_CHOSEN_LIMIT)]
    tool = ForgetChosenTool(store := await _store(*records), GLOBAL_MEMORY_SCOPE)
    assert len(await _card_lines(tool, _call())) == FORGET_CHOSEN_LIMIT + 1
    result = await tool.invoke(_call())
    assert result.is_error is False
    assert result.matched_nothing is False
    assert await _texts(store) == []


async def test_a_store_down_at_the_card_deletes_nothing() -> None:
    store = await _store(_record("card", _CARD))
    store.fail_with(MemoryStoreError("pgvector is down"))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    assert await tool.card(_call()) is None
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert _said(result) == (
        "the memory store is unavailable, so nothing was forgotten: pgvector is down"
    )


async def test_a_store_failing_the_delete_says_the_forget_failed() -> None:
    store = _FailingDelete()
    await store.add(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    await tool.card(_call())
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert _said(result) == "the memory store failed during the forget: pgvector is down"


async def test_an_invoke_without_a_card_deletes_nothing() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    result = await tool.invoke(_call())
    assert result.is_error is True
    assert _said(result) == "nothing was forgotten: no card listed what to delete"
    assert await _texts(store) == ["card"]


async def test_a_card_is_used_once() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    await tool.card(_call())
    await tool.invoke(_call())
    second = await tool.invoke(_call())
    assert _said(second) == "nothing was forgotten: no card listed what to delete"


async def test_only_the_latest_cards_are_kept() -> None:
    store = await _store(_record("card", _CARD))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    for index in range(33):
        await tool.card(_call(call_id=f"c{index}"))
    first = await tool.invoke(_call(call_id="c0"))
    assert _said(first) == "nothing was forgotten: no card listed what to delete"
    assert (await tool.invoke(_call(call_id="c1"))).is_error is False
