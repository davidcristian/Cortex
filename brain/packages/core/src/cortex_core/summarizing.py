"""A history window that recaps the turns it drops instead of losing them (ADR-0038 decision 9).

`CharBudgetHistoryWindow` bounds a turn's context by dropping the oldest turns whole. What the
user said in them is still in the store, but the model stops seeing it, so a long conversation
loses its own beginning. This window wraps that one and prepends a model-written recap of
everything the tail left behind. What the fold says to the model, and both fences around it,
live in `recap_prompt.py`.

The recap is cached behind `SessionStore`, keyed by the boundary it covers, and nothing lives in
a model process or its KV cache, so a swap between the write and the next read changes nothing
(the one hard rule). `docs/modules/brain-core.md` states the invariants this class is held to:
it only adds to the inner selection, it caches rather than recomputes, it releases the GPU lease
before the reply asks for it, it bounds what one fold may cost, it announces a pass it is really
going to make, and it reports why when it adds nothing.

One property is worth repeating here because the code below is where it is enforced: the model
pass goes through `drain_text`, which leaves the inference adapter's acquire block in a
`finally`. Selection runs to completion inside `assemble_inference_messages`, several statements
before `handle_turn` first iterates the reply's generator, so the reply's acquire is the second
acquire of a sequence and never a nested one under the non-reentrant lease.
"""

import logging
from collections.abc import Sequence

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.errors import InferenceError, SessionStoreError
from cortex_core.events import StatusUpdate
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.ports_stores import SessionStore
from cortex_core.progress import ProgressSink
from cortex_core.recap_prompt import (
    RECAP_BOUNDS,
    build_recap_messages,
    clean_recap,
    collapse_recap,
    fence_recap,
)
from cortex_core.sessions import HistoryRecap
from cortex_core.stops import StopLedger
from cortex_core.windowing import HistoryWindow

_logger = logging.getLogger(__name__)

# The StatusUpdate.state a fold's progress rides under, beside "thinking", "delegating" and
# "swapping": what the machine is doing, in the same voice. The detail is app-authored, so like
# every other progress line it needs no guardrail pass and cannot be steered by what was read.
RECAP_PROGRESS_STATE = "folding"
RECAP_PROGRESS_DETAIL = "summarizing the earlier part of this conversation"


class SummarizingHistoryWindow:
    """Wrap a history window so the turns it drops arrive as a cached, model-written recap.

    ``inner`` is the window that decides what to keep (``CharBudgetHistoryWindow`` in every
    shipped deployment); this class never alters that selection and never returns fewer messages
    than it did.

    ``min_dropped_chars`` is how much newly dropped conversation is worth a model pass. It is
    denominated in characters because that is the unit the budget it wraps is denominated in.
    Below it the fold is deferred, not skipped: the boundary the stored recap covers stays where
    it is, so the next fold that does run reads from there and picks up everything deferred since.
    What it costs while deferred is that those turns are in neither the recap nor the window, so
    for those turns the conversation reads as if the budget alone were shipping. ``0`` folds on
    every boundary move, which is the pre-addendum behaviour.
    """

    def __init__(
        self,
        inner: HistoryWindow,
        store: SessionStore,
        backend: InferenceBackend,
        model: str,
        clock: Clock,
        *,
        min_dropped_chars: int = 0,
    ) -> None:
        self._inner = inner
        self._store = store
        self._backend = backend
        self._model = model
        self._clock = clock
        self._min_dropped_chars = min_dropped_chars

    async def select(
        self,
        history: Sequence[Message],
        *,
        session_id: str,
        progress: ProgressSink | None = None,
    ) -> Sequence[Message]:
        """The inner window's selection, prefixed with a fenced recap of whatever it dropped.

        The prefix is a ``Role.SYSTEM`` message because that is where a turn's derived context
        goes, but its body is fenced data rather than trusted instruction, and ``fence_recap``
        is the only way one is built. It is stamped with the last turn the recap actually
        ACCOUNTS FOR rather than the boundary now, which are the same message until a fold is
        deferred and diverge afterwards.

        Returns the inner selection unchanged when nothing was dropped (a short conversation
        pays nothing and makes no model call) and whenever the recap cannot be produced. The
        two failures that reach here are the store being unreachable and the model being
        unreachable or failing mid-stream; both are logged and swallowed, because a turn that
        loses its recap still answers the user and a turn that raises does not.
        """
        kept = await self._inner.select(history, session_id=session_id)
        boundary = len(history) - len(kept)
        if boundary < 1:
            return kept
        try:
            recap = await self._recap(session_id, history, boundary, progress)
        except (InferenceError, SessionStoreError):
            _logger.warning(
                "history recap unavailable; falling back to the plain window",
                extra={"session_id": session_id, "boundary": boundary},
                exc_info=True,
            )
            return kept
        if recap is None:
            return kept
        preface = Message(
            role=Role.SYSTEM,
            text=fence_recap(recap.text),
            at=self._clock.now(),
            turn_id=history[recap.covers - 1].turn_id,
        )
        return (preface, *kept)

    async def _recap(
        self,
        session_id: str,
        history: Sequence[Message],
        boundary: int,
        progress: ProgressSink | None,
    ) -> HistoryRecap | None:
        """The recap to prepend: the stored one, a freshly folded one, or ``None``.

        ``None`` means there is nothing to prepend at all, which is a session's first boundary
        move when the fold was deferred or the model produced nothing usable. Neither is an
        error and neither is worth storing; the caller falls back to the plain window for this
        turn and tries again next time the boundary moves.
        """
        stored = await self._store.recap(session_id)
        if stored is not None and stored.covers == boundary:
            return stored
        # A stored recap covering MORE than the boundary is the one case that is not a fold: a
        # widened character budget pulled messages back into the window, so the old recap would
        # duplicate them. It is dropped and the prefix is recapped fresh, which self-heals on
        # the spot rather than staying wrong until the session ends.
        previous = stored if stored is not None and stored.covers < boundary else None
        start = previous.covers if previous is not None else 0
        newly_dropped = history[start:boundary]
        if sum(len(message.text) for message in newly_dropped) < self._min_dropped_chars:
            return previous
        if progress is not None:
            await progress.emit(
                StatusUpdate(state=RECAP_PROGRESS_STATE, detail=RECAP_PROGRESS_DETAIL)
            )
        prompt = build_recap_messages(
            previous,
            newly_dropped,
            at=self._clock.now(),
            turn_id=history[boundary - 1].turn_id,
        )
        stops = StopLedger()
        raw = await drain_text(self._backend, self._model, prompt, bounds=RECAP_BOUNDS, stops=stops)
        text = clean_recap(raw)
        if not text:
            # The two fields beside the message are the whole diagnosis, because the completion
            # itself is gone by the time anyone reads this (ADR-0038 cut-fold addendum).
            # ``capped`` separates the two causes with opposite fixes: True is the token budget
            # running out mid-account, which needs a larger RECAP_MAX_TOKENS or a smaller fold,
            # and False is a model that ended by itself in the wrong shape, which needs the
            # instruction rewritten. ``chars`` is the account's own length, measured the way the
            # rejection rules measure it, so it splits the other two causes: 0 is a model that
            # said nothing, and a number past RECAP_MAX is one that ran further than the store
            # will hold.
            _logger.warning(
                "the model returned no usable history recap; falling back to the plain window",
                extra={
                    "session_id": session_id,
                    "boundary": boundary,
                    "capped": stops.capped,
                    "chars": len(collapse_recap(raw)),
                },
            )
            return previous
        fresh = HistoryRecap(text=text, covers=boundary)
        await self._store.set_recap(session_id, fresh)
        return fresh
