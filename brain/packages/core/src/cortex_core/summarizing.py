"""A history window that recaps the turns it drops instead of losing them (ADR-0038 decision 9)."""

import logging
from collections.abc import Sequence

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.errors import InferenceError, SessionStoreError
from cortex_core.events import StatusUpdate
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.ports_stores import SessionStore
from cortex_core.progress import ProgressSink
from cortex_core.recap_prompt import RECAP_BOUNDS, build_recap_messages, clean_recap, fence_recap
from cortex_core.sessions import HistoryRecap
from cortex_core.windowing import HistoryWindow

_logger = logging.getLogger(__name__)

# The StatusUpdate.state a fold's progress rides under, beside "thinking", "delegating" and
# "swapping": what the machine is doing, in the same voice. The detail is app-authored, so like
# every other progress line it needs no guardrail pass and cannot be steered by what was read.
RECAP_PROGRESS_STATE = "folding"
RECAP_PROGRESS_DETAIL = "summarizing the earlier part of this conversation"


class SummarizingHistoryWindow:
    """Wrap a history window so the turns it drops arrive as a cached, model-written recap."""

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
        """The inner window's selection, prefixed with a fenced recap of whatever it dropped."""
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
        """The recap to prepend: the stored one, a freshly folded one, or ``None``."""
        stored = await self._store.recap(session_id)
        if stored is not None and stored.covers == boundary:
            return stored
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
        text = clean_recap(
            await drain_text(self._backend, self._model, prompt, bounds=RECAP_BOUNDS)
        )
        if not text:
            _logger.warning(
                "the model returned no usable history recap; falling back to the plain window",
                extra={"session_id": session_id, "boundary": boundary},
            )
            return previous
        fresh = HistoryRecap(text=text, covers=boundary)
        await self._store.set_recap(session_id, fresh)
        return fresh
