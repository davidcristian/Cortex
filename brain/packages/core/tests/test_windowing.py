"""Behavior of the char-budget history window (ADR-0014).

The summarizing window that wraps it lives in ``test_summarizing.py``.
"""

from datetime import UTC, datetime

import pytest

from cortex_core import CharBudgetHistoryWindow, Message, Role

_AT = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


def _turn(turn_id: str, user: str, assistant: str | None = None) -> list[Message]:
    messages = [Message(role=Role.USER, text=user, at=_AT, turn_id=turn_id)]
    if assistant is not None:
        messages.append(Message(role=Role.ASSISTANT, text=assistant, at=_AT, turn_id=turn_id))
    return messages


def test_rejects_a_non_positive_budget() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        CharBudgetHistoryWindow(0)


async def test_empty_history_stays_empty() -> None:
    assert await CharBudgetHistoryWindow(10).select((), session_id="s") == ()


async def test_under_budget_history_is_untouched() -> None:
    history = [*_turn("t1", "aa", "bb"), *_turn("t2", "cc", "dd")]
    assert await CharBudgetHistoryWindow(8).select(history, session_id="s") == tuple(history)


async def test_oldest_turns_drop_first_and_whole() -> None:
    history = [*_turn("t1", "aaaa", "bbbb"), *_turn("t2", "cc", "dd"), *_turn("t3", "e", "f")]
    # t3 (2 chars) + t2 (4) fit a budget of 6; t1 (8) would overflow and drops whole.
    selected = await CharBudgetHistoryWindow(6).select(history, session_id="s")
    assert [m.turn_id for m in selected] == ["t2", "t2", "t3", "t3"]


async def test_a_turn_is_never_split_mid_exchange() -> None:
    history = [*_turn("t1", "aaa", "bbb"), *_turn("t2", "cc", "dd")]
    # Budget 5 fits t2 (4) plus only ONE of t1's messages (3 each), so t1 must drop whole:
    # the model never sees an assistant reply without the user message it answered.
    selected = await CharBudgetHistoryWindow(5).select(history, session_id="s")
    assert [m.turn_id for m in selected] == ["t2", "t2"]


async def test_newest_turn_is_kept_even_when_oversized() -> None:
    history = [*_turn("t1", "aa", "bb"), *_turn("t2", "x" * 100, "y" * 100)]
    selected = await CharBudgetHistoryWindow(10).select(history, session_id="s")
    assert [m.turn_id for m in selected] == ["t2", "t2"]


async def test_current_turn_user_message_survives_alone() -> None:
    # At selection time the newest turn is the just-persisted user message, reply pending.
    history = [*_turn("t1", "old", "reply"), *_turn("t2", "the current question")]
    selected = await CharBudgetHistoryWindow(4).select(history, session_id="s")
    assert [m.text for m in selected] == ["the current question"]


async def test_selection_is_a_contiguous_tail_not_a_sieve() -> None:
    # The old-but-tiny t1 would fit the leftover budget, but a gap mid-history confuses
    # the model more than truncation: the walk stops at the first overflowing turn (t2).
    history = [*_turn("t1", "a", "b"), *_turn("t2", "x" * 50, "y" * 50), *_turn("t3", "cc", "dd")]
    selected = await CharBudgetHistoryWindow(10).select(history, session_id="s")
    assert [m.turn_id for m in selected] == ["t3", "t3"]
