"""A history window that recaps the turns it drops instead of losing them (ADR-0038 decision 9).

`CharBudgetHistoryWindow` bounds a turn's context by dropping the oldest turns whole. What the
user said in them is still in the store, but the model stops seeing it, so a long conversation
forgets its own beginning. This window wraps that one and prepends a model-written recap of
everything the tail left behind, so the beginning survives as a paragraph instead of vanishing.

Three properties make it safe to run on the turn's critical path:

**It can only add.** The wrapped window's selection is returned untouched; the recap is a system
message PREPENDED to it. Every failure path (the store unreachable, the model unreachable, the
model saying nothing usable) returns that selection exactly as the shipped window would have. So
a broken summarizer costs the user context it might have added, never a word they actually wrote.

**It caches rather than recomputes.** The recap lives in Redis behind `SessionStore`, keyed by
the boundary it covers. History is append-only, so a recap of a prefix can only go incomplete,
never wrong: when the boundary moves the previous recap is folded together with the newly dropped
turns rather than recomputed from scratch, and while the boundary is still where it was, a turn
pays nothing. Nothing lives in the model process or its KV cache, so a swap between the write and
the next read is invisible: the next model rehydrates it from the store like any other state.

**It lets go of the GPU before the reply asks for it.** The model pass goes through `drain_text`,
which leaves the inference adapter's acquire block in a `finally`. Selection runs to completion
inside `assemble_inference_messages`, several statements before `handle_turn` first iterates the
reply's generator, so the reply's acquire is the second acquire of a sequence and never a nested
one under the non-reentrant lease.
"""

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
    """The one-message prompt for a recap: the instruction, the previous recap, the new turns.

    ``previous`` is the recap being folded forward (``None`` for a session's first recap, and
    for the self-healing case where a stored recap covers more than the boundary now does, which
    a widened character budget can produce). Including it is what makes this a rolling fold
    rather than a re-read of the whole prefix: the model sees one paragraph plus the handful of
    turns that have dropped since, never the entire conversation.
    """
    parts = [_INSTRUCTION]
    if previous is not None:
        parts.append(f"The account so far:\n{previous.text}")
    transcript = "\n".join(f"{message.role.value}: {message.text}" for message in dropped)
    parts.append(f"What has dropped out of context since:\n{transcript}")
    return [Message(role=Role.USER, text="\n\n".join(parts), at=at, turn_id=turn_id)]


def clean_recap(raw: str) -> str:
    """Collapse the model's reply to one paragraph and bound it to ``RECAP_MAX``.

    An empty result (the model said nothing usable, or a reasoning model spent its whole budget
    thinking) comes back as ``""`` for the caller to reject rather than store, the ``clean_title``
    convention. The bound is what keeps a runaway reply from eating the context the window exists
    to protect.
    """
    return " ".join(raw.split())[:RECAP_MAX]


class SummarizingHistoryWindow:
    """Wrap a history window so the turns it drops arrive as a cached, model-written recap.

    ``inner`` is the window that decides what to keep (``CharBudgetHistoryWindow`` in every
    shipped deployment); this class never second-guesses it and never returns fewer messages
    than it did.
    """

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
        """The inner window's selection, prefixed with a recap of whatever it dropped.

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
        """The recap covering ``boundary`` messages: the stored one, or a freshly folded one.

        ``None`` means the model produced nothing usable, which is not an error and not worth
        storing; the caller falls back to the plain window for this turn and tries again next
        time the boundary moves.
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
