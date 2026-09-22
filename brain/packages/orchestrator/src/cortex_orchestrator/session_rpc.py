"""Session catalog RPCs: store views onto the wire, plus the user-only rename write."""

from datetime import datetime

from cortex_core import Message, SessionMemoryCascade, SessionStore, SessionSummary
from cortex_seam import DeleteSessionReply, RenameSessionReply, SetSessionHoistedReply
from cortex_seam import SessionMessage as SessionMessagePb
from cortex_seam import SessionSummary as SessionSummaryPb

DEFAULT_SESSION_LIST_LIMIT = 50
MAX_SESSION_LIST_LIMIT = 200
# A bound applied at the wire edge, so no unbounded label reaches the store. Generous on
# purpose: the switcher re-collapses and re-truncates the display at read.
MAX_TITLE_INPUT = 200


def unix_ms(moment: datetime) -> int:
    """A tz-aware instant as unix-milliseconds, which is the wire's timestamp form."""
    return int(moment.timestamp() * 1000)


def summary_to_proto(summary: SessionSummary) -> SessionSummaryPb:
    """Map a core `SessionSummary` to the wire message."""
    return SessionSummaryPb(
        session_id=summary.session_id,
        title=summary.title,
        preview=summary.preview,
        last_activity_unix_ms=unix_ms(summary.last_activity),
        hoisted=summary.hoisted,
    )


def message_to_proto(message: Message) -> SessionMessagePb:
    """Map a persisted `Message` to the wire `SessionMessage`."""
    return SessionMessagePb(
        role=message.role.value,
        text=message.text,
        turn_id=message.turn_id,
        at_unix_ms=unix_ms(message.at),
    )


def clamp_limit(limit: int) -> int:
    """A `ListSessions` `limit`: 0/negative → the default, and never above the hard cap."""
    if limit <= 0:
        return DEFAULT_SESSION_LIST_LIMIT
    return min(limit, MAX_SESSION_LIST_LIMIT)


def clamp_title(title: str) -> str:
    """Bound an accepted rename to `MAX_TITLE_INPUT` characters, at the wire edge."""
    return title[:MAX_TITLE_INPUT]


async def rename_session(store: SessionStore, session_id: str, title: str) -> RenameSessionReply:
    """Persist a user-chosen display title for one chat; `""` clears the override."""
    await store.set_title(session_id, clamp_title(title))
    return RenameSessionReply()


async def delete_session(
    store: SessionStore, cascade: SessionMemoryCascade | None, session_id: str
) -> DeleteSessionReply:
    """Delete one chat and cascade to its private memories."""
    # The chat goes first, because that is the user's primary intent: a memory failure then
    # leaves the chat gone with a retry cleaning the memories, rather than a visible chat whose
    # memories vanished. Both steps are idempotent, so a retry after any failure is safe.
    await store.delete(session_id)
    if cascade is not None:
        await cascade.delete_session_memories(session_id)
    return DeleteSessionReply()


async def set_session_hoisted(
    store: SessionStore, session_id: str, *, hoisted: bool
) -> SetSessionHoistedReply:
    """Add or remove one chat from the hoisted set: a user-only catalog write."""
    await store.set_hoisted(session_id, hoisted=hoisted)
    return SetSessionHoistedReply()
