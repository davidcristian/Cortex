"""A history window that recaps the turns it drops instead of losing them (ADR-0038 decision 9)."""

import logging
from collections.abc import Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.drain import drain_text
from cortex_core.errors import InferenceError, SessionStoreError
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.ports_stores import SessionStore
from cortex_core.sessions import RECAP_MAX, HistoryRecap
from cortex_core.windowing import HistoryWindow

_logger = logging.getLogger(__name__)

# The instruction the recap pass runs under. It asks for the facts a follow-up question would
# need rather than a description of the conversation, because "the user asked about their flight"
# is exactly the shape of summary that loses the flight number.
_INSTRUCTION = (
    "Below is the earlier part of a conversation that no longer fits in context. Write a "
    "compact account of it for the assistant to rely on when answering what comes next. Keep "
    "every concrete detail a later question might depend on: names, numbers, dates, decisions, "
    "preferences the user stated, and anything left unresolved. Drop pleasantries and repetition. "
    "Write plain prose, no headings and no list markers, and reply with the account only."
)

# How the recap is introduced to the model in the turn it rides on. It is the assistant's own
# notes about the conversation so far, not user speech and not a tool result, so it goes in as
# system context beside the other derived context the turn assembles.
_PREFACE = "Summary of the earlier part of this conversation, which is no longer shown in full:"


def build_recap_messages(
    previous: HistoryRecap | None,
    dropped: Sequence[Message],
    *,
    at: datetime,
    turn_id: str,
) -> list[Message]:
    """The one-message prompt for a recap: the instruction, the previous recap, the new turns."""
    parts = [_INSTRUCTION]
    if previous is not None:
        parts.append(f"The account so far:\n{previous.text}")
    transcript = "\n".join(f"{message.role.value}: {message.text}" for message in dropped)
    parts.append(f"What has dropped out of context since:\n{transcript}")
    return [Message(role=Role.USER, text="\n\n".join(parts), at=at, turn_id=turn_id)]


def clean_recap(raw: str) -> str:
    """Collapse the model's reply to one paragraph and bound it to ``RECAP_MAX``."""
    return " ".join(raw.split())[:RECAP_MAX]


class SummarizingHistoryWindow:
    """Wrap a history window so the turns it drops arrive as a cached, model-written recap."""

    def __init__(
        self,
        inner: HistoryWindow,
        store: SessionStore,
        backend: InferenceBackend,
        model: str,
        clock: Clock,
    ) -> None:
        self._inner = inner
        self._store = store
        self._backend = backend
        self._model = model
        self._clock = clock

    async def select(self, history: Sequence[Message], *, session_id: str) -> Sequence[Message]:
        """The inner window's selection, prefixed with a recap of whatever it dropped."""
        kept = await self._inner.select(history, session_id=session_id)
        boundary = len(history) - len(kept)
        if boundary < 1:
            return kept
        try:
            recap = await self._recap(session_id, history, boundary)
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
            text=f"{_PREFACE}\n{recap.text}",
            at=self._clock.now(),
            # The recap stands in for the messages up to the boundary, so it is stamped with
            # the last turn it accounts for rather than with the turn now being answered.
            turn_id=history[boundary - 1].turn_id,
        )
        return (preface, *kept)

    async def _recap(
        self, session_id: str, history: Sequence[Message], boundary: int
    ) -> HistoryRecap | None:
        """The recap covering ``boundary`` messages: the stored one, or a freshly folded one."""
        stored = await self._store.recap(session_id)
        if stored is not None and stored.covers == boundary:
            return stored
        previous = stored if stored is not None and stored.covers < boundary else None
        start = previous.covers if previous is not None else 0
        prompt = build_recap_messages(
            previous,
            history[start:boundary],
            at=self._clock.now(),
            turn_id=history[boundary - 1].turn_id,
        )
        text = clean_recap(await drain_text(self._backend, self._model, prompt))
        if not text:
            _logger.warning(
                "the model returned no usable history recap; falling back to the plain window",
                extra={"session_id": session_id, "boundary": boundary},
            )
            return None
        fresh = HistoryRecap(text=text, covers=boundary)
        await self._store.set_recap(session_id, fresh)
        return fresh
