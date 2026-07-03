"""Session-history windowing: bound what one turn sends to the model (ADR-0014).

`TurnEngine` reads a session's FULL history from the store every turn (the one hard
rule, where the store stays the sole source of truth), but what it hands the backend must
fit the resident model's context window. A `HistoryWindow` is the pure selection
policy between the two, applied at inference-message assembly only: persistence is
untouched and the selection is derived fresh each turn, so it is never stored, nothing to
rehydrate. Summarization (compressing old turns instead of dropping them) is a
still-deferred refinement behind this same seam (ROADMAP, Slice 3 block).
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.conversation import Message


class HistoryWindow(Protocol):
    """Selects the slice of a session's stored history one turn sends to the model.

    ``select`` returns a subsequence of ``history`` in original order. Implementations
    must keep the newest turn (its user message is the query driving this turn)
    whatever their budget; an empty history stays empty.
    """

    def select(self, history: Sequence[Message]) -> Sequence[Message]: ...


class CharBudgetHistoryWindow:
    """Keep the newest whole turns whose summed text length fits a character budget.

    Characters stand in for tokens (roughly 4 chars/token) so the core needs no
    tokenizer. The budget is a conservative heuristic sized well under the model
    context, not an exact fit (ADR-0014). Selection groups messages into turns
    (consecutive ``turn_id``), walks from the newest backward, and stops at the first
    turn that would overflow: the model sees a contiguous tail of history, turns kept
    or dropped whole. There is never an assistant reply without its user message, and never a
    gap mid-history. The newest turn is always kept, oversized or not: the current
    user message must reach the model.
    """

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
