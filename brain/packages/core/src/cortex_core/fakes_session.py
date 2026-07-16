"""In-memory ``SessionStore`` fake: the contract twin of the Redis adapter (``cortex_session``)."""

from collections.abc import Sequence

from cortex_core.conversation import Message
from cortex_core.sessions import SessionSummary, merge_pinned, summarize_session


class InMemorySessionStore:
    """SessionStore held in dicts/sets and meant for tests and single-process experiments only.

    It intentionally does NOT survive a process restart; the Redis adapter is the
    runtime store precisely because this one cannot prove the hard rule.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}
        self._titles: dict[str, str] = {}
        self._pinned: set[str] = set()

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message at the end of the session's history."""
        self._sessions.setdefault(session_id, []).append(message)

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        return tuple(self._sessions.get(session_id, ()))

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return recent chats plus every pinned chat, pinned-first (ADR-0021 pinning addendum)."""
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
        """Hard-delete a session's history, title, and pin, idempotently (delete addendum)."""
        self._sessions.pop(session_id, None)
        self._titles.pop(session_id, None)
        self._pinned.discard(session_id)

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        """Pin or unpin a chat (ADR-0021 pinning addendum); idempotent by value."""
        if pinned:
            self._pinned.add(session_id)
        else:
            self._pinned.discard(session_id)
