from collections.abc import Sequence
from datetime import UTC, datetime

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    MemoryStoreError,
    ToolCall,
    ToolResult,
    TurnStamp,
)

_AT = datetime(2026, 11, 7, 1, 0, 0, tzinfo=UTC)
_OLD = "User: Remember that my phone number is 0612345678.\nAssistant: Noted."
_NONE_FOUND = (
    "nothing was forgotten: no remembered exchange contains that text, so tell the user that "
    "nothing about it was stored, and do not ask the user for the value"
)
_ALREADY_DELETED = (
    "nothing more was forgotten: no remembered exchange contains that text, and an earlier call "
    "in this turn already deleted what the user asked to forget, so tell the user it was deleted "
    "and do not say that it was not stored or could not be found"
)


def _record(record_id: str, text: str) -> MemoryRecord:
    return MemoryRecord(id=record_id, text=text, embedding=(1.0, 0.0), at=_AT, scope="global")


async def _tool(
    *records: MemoryRecord, store: InMemoryMemoryStore | None = None
) -> ForgetChosenTool:
    held = store or InMemoryMemoryStore()
    for record in records:
        await held.add(record)
    return ForgetChosenTool(held, GLOBAL_MEMORY_SCOPE)


def _call(text: str, call_id: str, turn: str = "turn-a") -> ToolCall:
    return ToolCall(
        id=call_id,
        name=FORGET_CHOSEN_TOOL_NAME,
        arguments={"text": text},
        stamp=TurnStamp(session_id="chat-a", turn_id=turn),
    )


async def _run(tool: ForgetChosenTool, call: ToolCall) -> ToolResult:
    await tool.card(call)
    return await tool.invoke(call)


def _said(result: ToolResult) -> str:
    assert result.content.endswith(".")
    return result.content.removesuffix(".")


class _FailingDelete(InMemoryMemoryStore):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        del ids
        msg = "pgvector is down"
        raise MemoryStoreError(msg)


async def test_a_later_unmatched_call_in_the_turn_names_the_earlier_delete() -> None:
    tool = await _tool(_record("old", _OLD))
    assert (await _run(tool, _call("0612345678", "c1"))).is_error is False
    later = await _run(tool, _call("0699000000", "c2"))
    assert _said(later) == _ALREADY_DELETED
    assert later.is_error is False
    assert later.matched_nothing is False


async def test_a_repeat_of_the_deleting_text_names_the_delete_too() -> None:
    tool = await _tool(_record("old", _OLD))
    await _run(tool, _call("0612345678", "c1"))
    assert _said(await _run(tool, _call("0612345678", "c2"))) == _ALREADY_DELETED


async def test_an_unmatched_call_in_a_later_turn_says_nothing_was_stored() -> None:
    tool = await _tool(_record("old", _OLD))
    await _run(tool, _call("0612345678", "c1"))
    later = await _run(tool, _call("0612345678", "c2", turn="turn-b"))
    assert _said(later) == _NONE_FOUND
    assert later.matched_nothing is True


async def test_unmatched_calls_with_no_delete_both_say_nothing_was_stored() -> None:
    tool = await _tool(_record("old", _OLD))
    for call_id in ("c1", "c2"):
        result = await _run(tool, _call("passport", call_id))
        assert _said(result) == _NONE_FOUND
        assert result.matched_nothing is True


async def test_a_failed_delete_leaves_the_turn_without_a_delete() -> None:
    tool = await _tool(_record("old", _OLD), store=_FailingDelete())
    failed = await _run(tool, _call("0612345678", "c1"))
    assert _said(failed) == "the memory store failed during the forget: pgvector is down"
    assert _said(await _run(tool, _call("passport", "c2"))) == _NONE_FOUND


async def test_a_later_call_matching_another_row_still_shows_a_card() -> None:
    store = InMemoryMemoryStore()
    tool = await _tool(_record("old", _OLD), _record("pin", "User: my PIN is 5521."), store=store)
    await _run(tool, _call("0612345678", "c1"))
    later = _call("5521", "c2")
    assert await tool.card(later) is not None
    assert _said(await tool.invoke(later)).startswith("forgot 1 remembered exchanges")
    assert list(await store.search((1.0, 0.0), k=10)) == []


async def test_only_the_latest_turns_keep_their_delete() -> None:
    tool = await _tool(*(_record(f"r{index}", f"note {index:02d}") for index in range(33)))
    for index in range(33):
        await _run(tool, _call(f"note {index:02d}", f"c{index}", turn=f"t{index}"))
    assert _said(await _run(tool, _call("passport", "x0", turn="t0"))) == _NONE_FOUND
    assert _said(await _run(tool, _call("passport", "x1", turn="t1"))) == _ALREADY_DELETED
