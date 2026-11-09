from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_LIMIT,
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    MemoryRecord,
    MemoryStoreError,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_count_note import FORGOT_COUNT_NOTE, FORGOT_COUNT_NOTES, forgot_count_note
from cortex_core.stops import StopLedger
from cortex_core.tools import TurnStamp

NAMES_NO_REMOVAL = [
    "I've updated your gym locker number to 5521.",
    "I've changed your gym locker number.",
    "I've saved that.",
    "Should I forget your gym locker number?",
    "I haven't forgotten your gym locker number.",
    "Nothing was removed from my memory.",
    "OK.",
]
NAMES_REMOVAL = [
    "I've forgotten your gym locker number.",
    "I've removed that from my memory.",
    "Your gym locker number has been deleted.",
    "OK. I've forgotten your gym locker number.",
    "J'ai oublié ton numéro de casier.",
    "Ich habe die Schranknummer vergessen.",
    "He olvidado tu número de taquilla.",
    "Am uitat numărul dulapului.",
]


def _closed(reply: str, deleted: int, query: str = "Forget my gym locker number.") -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_deleted=deleted)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_reply_naming_no_removal_after_a_delete_ends_with_the_count(reply: str) -> None:
    shown = _closed(reply, 2)
    assert shown.startswith(reply)
    assert shown.endswith(FORGOT_COUNT_NOTE.format(count=2))


@pytest.mark.parametrize("reply", NAMES_REMOVAL)
def test_a_reply_naming_the_removal_in_any_note_language_gets_no_count(reply: str) -> None:
    assert _closed(reply, 2) == reply


@pytest.mark.parametrize("reply", NAMES_NO_REMOVAL)
def test_a_turn_that_deleted_nothing_gets_no_count(reply: str) -> None:
    assert FORGOT_COUNT_NOTE.format(count=0) not in _closed(reply, 0)


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie mon numéro de casier.", "fr"),
        ("Vergiss meine Schranknummer.", "de"),
        ("Olvida mi número de taquilla, por favor.", "es"),
        ("Uită numărul meu de dulap.", "ro"),
    ],
)
def test_the_count_is_written_in_the_language_of_the_message(query: str, language: str) -> None:
    note = FORGOT_COUNT_NOTES[language].format(count=1)
    assert _closed("OK.", 1, query) == "OK." + note
    assert forgot_count_note(1, language) == note


def _row(record_id: str, text: str, minutes: int) -> MemoryRecord:
    at = datetime(2026, 11, 9, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=minutes)
    return MemoryRecord(id=record_id, text=text, embedding=(1.0, 0.0), at=at)


def _call(text: str, query: str) -> ToolCall:
    stamp = TurnStamp(session_id="chat-a", turn_id="t1", query=query)
    return ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text}, stamp=stamp)


async def test_a_delete_that_left_more_rows_holding_the_value_still_counts_its_rows() -> None:
    store = InMemoryMemoryStore()
    await store.add(_row("gym", "User: Remember my gym locker number 5521.\nAssistant: Noted.", 0))
    for index in range(FORGET_CHOSEN_LIMIT + 1):
        shed = f"User: The number for shed {index} is 5521.\nAssistant: Noted."
        await store.add(_row(f"shed{index}", shed, index + 1))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call("number 5521", "Forget my gym locker number 5521.")
    await tool.card(call)
    result = await tool.invoke(call)
    assert result.is_error
    assert result.numbers_left is None
    assert result.forgot == 1


async def test_a_delete_that_rows_written_since_the_card_outlast_still_counts_its_rows() -> None:
    store = InMemoryMemoryStore()
    await store.add(_row("gym", "User: Remember my gym locker number 5521.\nAssistant: Noted.", 0))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call("gym locker", "Forget my gym locker number.")
    await tool.card(call)
    await store.add(_row("new", "User: My gym locker is by the door.\nAssistant: Noted.", 5))
    result = await tool.invoke(call)
    assert result.is_error
    assert result.numbers_left is None
    assert result.forgot == 1


class _FailingAfterDelete(InMemoryMemoryStore):
    async def delete_ids(self, ids: Sequence[str]) -> int:
        removed = await super().delete_ids(ids)
        self.fail_with(MemoryStoreError("pgvector is down"))
        return removed


async def test_a_store_failing_after_the_delete_still_counts_the_rows_it_removed() -> None:
    store = _FailingAfterDelete()
    await store.add(_row("gym", "User: Remember my gym locker number 5521.\nAssistant: Noted.", 0))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    call = _call("gym locker", "Forget my gym locker number.")
    await tool.card(call)
    result = await tool.invoke(call)
    assert (result.is_error, result.forgot, result.numbers_left) == (True, 1, None)
    assert result.content.startswith("forgot 1 remembered exchanges, but the memory store then")
    assert "forget" not in result.content.split(",", 1)[1]
