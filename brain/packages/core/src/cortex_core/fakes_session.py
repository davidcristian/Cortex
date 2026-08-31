"""In-memory ``SessionStore``, tested against the same contract as the Redis adapter."""

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
    """SessionStore held in dicts/sets and meant for tests and single-process experiments only."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}
        self._titles: dict[str, str] = {}
        self._pinned: set[str] = set()
        self._recaps: dict[str, HistoryRecap] = {}

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message at the end of the session's history."""
        if message.images:
            msg = "a session store never persists images: pixels are turn-local"
            raise SessionStoreError(msg)
        self._sessions.setdefault(session_id, []).append(message)

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        return tuple(self._sessions.get(session_id, ()))

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return the recent chats plus every ``pinned`` chat, those first."""
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
        """Persist a brain-generated display title, preferred by ``list_sessions``."""
        self._titles[session_id] = title

    async def delete(self, session_id: str) -> None:
        """Idempotently delete a chat for good: messages, title, ``pinned`` flag and recap."""
        self._sessions.pop(session_id, None)
        self._titles.pop(session_id, None)
        self._pinned.discard(session_id)
        self._recaps.pop(session_id, None)

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        """Persist the summarizing window's recap of this session's dropped prefix."""
        self._recaps[session_id] = recap

    async def recap(self, session_id: str) -> HistoryRecap | None:
        """The stored recap, or ``None`` for a session that has never had one written."""
        return self._recaps.get(session_id)

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        """Set or clear a chat's ``pinned`` flag; idempotent by value."""
        if pinned:
            self._pinned.add(session_id)
        else:
            self._pinned.discard(session_id)
