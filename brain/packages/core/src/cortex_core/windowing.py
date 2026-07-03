"""Session-history windowing: bound what one turn sends to the model (ADR-0014)."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.conversation import Message


class HistoryWindow(Protocol):
    """Selects the slice of a session's stored history one turn sends to the model."""

    def select(self, history: Sequence[Message]) -> Sequence[Message]: ...


class CharBudgetHistoryWindow:
    """Keep the newest whole turns whose summed text length fits a character budget."""

    def __init__(self, max_chars: int) -> None:
        if max_chars < 1:
            msg = "max_chars must be at least 1"
            raise ValueError(msg)
        self._max_chars = max_chars

    def select(self, history: Sequence[Message]) -> Sequence[Message]:
        """The newest whole turns fitting the budget (the newest always among them)."""
        turns: list[list[Message]] = []
        for message in history:
            if turns and turns[-1][-1].turn_id == message.turn_id:
                turns[-1].append(message)
            else:
                turns.append([message])
        remaining = self._max_chars
        kept: list[list[Message]] = []
        for turn in reversed(turns):
            cost = sum(len(message.text) for message in turn)
            if kept and cost > remaining:
                break
            kept.append(turn)
            remaining -= cost
        return tuple(message for turn in reversed(kept) for message in turn)
