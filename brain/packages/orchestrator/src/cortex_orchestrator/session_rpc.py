"""Session catalog RPCs (ADR-0021): store views onto the wire, plus the gated rename write."""

from datetime import datetime

from cortex_core import Message, SessionStore, SessionSummary
from cortex_seam import RenameSessionReply
from cortex_seam import SessionMessage as SessionMessagePb
from cortex_seam import SessionSummary as SessionSummaryPb

# Default and hard cap for a `ListSessions` request's `limit` (ADR-0021); a request's 0
# (or negative) means "server default", and no client can ask for an unbounded list.
DEFAULT_SESSION_LIST_LIMIT = 50
MAX_SESSION_LIST_LIMIT = 200
MAX_TITLE_INPUT = 200


def unix_ms(moment: datetime) -> int:
    """A tz-aware instant as unix-milliseconds (the seam's timestamp form, ADR-0021)."""
    return int(moment.timestamp() * 1000)


def summary_to_proto(summary: SessionSummary) -> SessionSummaryPb:
    """Map a core `SessionSummary` to the wire message (ADR-0021)."""
    return SessionSummaryPb(
        session_id=summary.session_id,
        title=summary.title,
        preview=summary.preview,
        last_activity_unix_ms=unix_ms(summary.last_activity),
    )


def message_to_proto(message: Message) -> SessionMessagePb:
    """Map a persisted `Message` to the wire `SessionMessage` (ADR-0021)."""
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
    """Bound an accepted rename to `MAX_TITLE_INPUT` characters (a seam-edge write guard)."""
    return title[:MAX_TITLE_INPUT]


async def rename_session(store: SessionStore, session_id: str, title: str) -> RenameSessionReply:
    """Persist a user-chosen display title for one chat; `""` clears the override (ADR-0021)."""
    await store.set_title(session_id, clamp_title(title))
    return RenameSessionReply()
