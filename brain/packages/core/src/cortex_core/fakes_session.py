"""In-memory ``SessionStore`` fake: the contract twin of the Redis adapter (``cortex_session``).

Split out of ``fakes.py`` to keep both under the line cap (the ``fakes_body``/``fakes_schedule``
precedent), and because the session store is the one fake carrying real read-path logic (the
pinned/recency union, ADR-0021 pinning addendum) rather than a dict passthrough. Like the other
in-memory fakes it does NOT survive a process restart; the Redis adapter is what proves the hard
rule, and this twin only has to be observably interchangeable with it behind the ``SessionStore``
port.
"""

from collections.abc import Sequence

from cortex_core.conversation import Message
from cortex_core.errors import SessionStoreError
from cortex_core.sessions import (
    HistoryRecap,
    SessionSummary,
    merge_pinned,
    summarize_session,
)


class InMemorySessionStore:
    """SessionStore held in dicts/sets and meant for tests and single-process experiments only.

    It intentionally does NOT survive a process restart; the Redis adapter is the
    runtime store precisely because this one cannot prove the hard rule.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}
        self._titles: dict[str, str] = {}
        self._pinned: set[str] = set()
        self._recaps: dict[str, HistoryRecap] = {}

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message at the end of the session's history.

        Refuses an image-bearing message, exactly as the Redis adapter does (ADR-0029): a fake
        that accepted what the real store rejects would let the turn-local invariant pass CI
        and fail in production.
        """
        if message.images:
            msg = "a session store never persists images: pixels are turn-local"
            raise SessionStoreError(msg)
        self._sessions.setdefault(session_id, []).append(message)

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        return tuple(self._sessions.get(session_id, ()))

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return recent chats plus every pinned chat, pinned-first (ADR-0021 pinning addendum).

        Every stored session has at least one message (a key exists only after an append),
        so each summarizes; a stored title (``set_title``) overrides the first-message one, and
        ``set_pinned`` sets each summary's ``pinned`` flag. The result is the newest ``limit`` by
        recency UNIONED with the pinned set (deduplicated), so a pinned chat older than the window
        still lists; ``merge_pinned`` then orders it pinned-first, recency-descending in each group.
        Ties on ``last_activity`` keep insertion order (unspecified, as for the Redis twin, since
        the contract test uses distinct timestamps)."""
        summaries = [
            summarize_session(
                session_id,
                messages,
                title_override=self._titles.get(session_id),
                pinned=session_id in self._pinned,
            )
            for session_id, messages in self._sessions.items()
        ]
        by_recency = sorted(summaries, key=lambda summary: summary.last_activity, reverse=True)
        window = by_recency[:limit]
        window_ids = {summary.session_id for summary in window}
        pinned_extra = [
            summary
            for summary in by_recency
            if summary.pinned and summary.session_id not in window_ids
        ]
        return merge_pinned([*window, *pinned_extra])

    async def set_title(self, session_id: str, title: str) -> None:
        """Persist a brain-generated display title, preferred by ``list_sessions`` (ADR-0021)."""
        self._titles[session_id] = title

    async def delete(self, session_id: str) -> None:
        """Hard-delete a session's history, title, pin and recap, idempotently (delete addendum)."""
        self._sessions.pop(session_id, None)
        self._titles.pop(session_id, None)
        self._pinned.discard(session_id)
        self._recaps.pop(session_id, None)

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        """Persist the summarizing window's recap of this session's dropped prefix.

        Last write wins, as for the Redis twin: a recap is re-derived whenever the window's
        boundary moves, and the newer one covers strictly more of the same append-only log.
        """
        self._recaps[session_id] = recap

    async def recap(self, session_id: str) -> HistoryRecap | None:
        """The stored recap, or ``None`` for a session that has never had one written."""
        return self._recaps.get(session_id)

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        """Pin or unpin a chat (ADR-0021 pinning addendum); idempotent by value.

        A pinned chat is unioned into ``list_sessions`` regardless of recency and sorts above the
        recency group. Pinning an unknown/absent id is benign (it lists only once it has messages),
        mirroring how the Redis twin's pinned set can hold a member with no message list."""
        if pinned:
            self._pinned.add(session_id)
        else:
            self._pinned.discard(session_id)
