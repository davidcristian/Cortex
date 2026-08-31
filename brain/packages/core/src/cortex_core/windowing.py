"""Session-history windowing: bound what one turn sends to the model (ADR-0014).

`TurnEngine` reads a session's FULL history from the store every turn (the one hard
rule, where the store stays the sole source of truth), but what it hands the backend must
fit the resident model's context window. A `HistoryWindow` is the selection
policy between the two, applied at inference-message assembly only: persistence is
untouched and, for the heuristic windows here, the selection is derived fresh each turn.
A window that recaps what it drops instead of losing it lives in `summarizing.py`, behind
this same seam (ADR-0038 decision 9).
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.conversation import Message
from cortex_core.progress import ProgressSink


class HistoryWindow(Protocol):
    """Selects the slice of a session's stored history one turn sends to the model.

    ``select`` returns the messages this turn's model sees, the newest turn among them
    whatever the budget (its user message is the query driving this turn); an empty history
    stays empty. A heuristic window returns a subsequence of ``history`` in original order,
    which is what ``CharBudgetHistoryWindow`` does; a window is also allowed to PREPEND
    derived context of its own, which is what the summarizing window does with its recap,
    and it may never drop or alter a kept message.

    ``select`` is ``async`` and carries ``session_id`` because a window may consult the
    store or the model (ADR-0038 decision 9): the recap of a session's dropped prefix is
    cached per session, so a window needs to know which session it is windowing.

    ``progress`` (ADR-0038 cheap-fold addendum) is the turn's side channel, so a window whose
    selection costs a model pass can say so while the user waits. It is handed per CALL, like
    the sink on a dispatch's ``TurnStamp`` and unlike a constructor dependency, because a sink
    belongs to one ``Converse`` stream while a window is a policy: passing it in keeps a shared
    window instance correct for every stream instead of relying on one being built per stream.
    ``None`` (the default, and every caller with no stream) emits nowhere. A heuristic
    implementation ignores both keywords and wraps a synchronous body.
    """

    async def select(
        self,
        history: Sequence[Message],
        *,
        session_id: str,
        progress: ProgressSink | None = None,
    ) -> Sequence[Message]: ...


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

    async def select(
        self,
        history: Sequence[Message],
        *,
        session_id: str,
        progress: ProgressSink | None = None,
    ) -> Sequence[Message]:
        """The newest whole turns fitting the budget (the newest always among them).

        Pure and synchronous in substance; the coroutine is the port's shape rather than this
        policy's need. ``session_id`` names a session this policy never consults, and
        ``progress`` a stream it has nothing to report on, since counting characters costs
        the user no wait worth narrating.
        """
        del session_id, progress
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
