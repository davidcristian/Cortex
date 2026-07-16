"""Session catalog RPCs (ADR-0021): store views onto the wire, plus the gated rename write.

The mapping + input-guard half of `ListSessions` / `GetSessionMessages` / `RenameSession`, kept
beside `server.py` so the servicer stays a thin binding (the `reminders.py` precedent).

`RenameSession` is a gated WRITE on the catalog, and its gate is not the mid-turn Confirmer.
The Confirmer (ADR-0022) exists to stop a possibly-jailbroken *model* from running an
irreversible tool call inside a turn; it is bound one-per-`Converse`-stream and round-trips a
card over that stream. A rename is the opposite trigger: the user clicks a control in the
overlay, out of band from any turn. It is no tool in any registry and never runs through the
turn engine, so no model, tool, or tainted turn can reach it. That structural user-only path IS
the gate for a user-initiated management action. It persists a derived DISPLAY title via
`SessionStore.set_title` (the catalog write the brain-generated-titles work already
contract-tested), never conversation content, so it stays within the one hard rule. A
`SessionStoreError` propagates for the servicer to abort `UNAVAILABLE` (the session-read
precedent).
"""

from datetime import datetime

from cortex_core import Message, SessionMemoryCascade, SessionStore, SessionSummary
from cortex_seam import DeleteSessionReply, RenameSessionReply
from cortex_seam import SessionMessage as SessionMessagePb
from cortex_seam import SessionSummary as SessionSummaryPb

# Default and hard cap for a `ListSessions` request's `limit` (ADR-0021); a request's 0
# (or negative) means "server default", and no client can ask for an unbounded list.
DEFAULT_SESSION_LIST_LIMIT = 50
MAX_SESSION_LIST_LIMIT = 200
# A seam-edge bound on an accepted rename, so no unbounded label reaches the store however the
# overlay behaves. It is generous on purpose: the display is re-collapsed to one line and
# re-truncated to `TITLE_MAX` at read (`cortex_core.sessions`), so this only caps what is
# persisted, never what the switcher shows.
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
    """Persist a user-chosen display title for one chat; `""` clears the override (ADR-0021).

    Reuses `SessionStore.set_title` (the catalog write behind brain-generated titles), bounding
    the label here so an unbounded value never reaches the store. A `SessionStoreError`
    propagates for the servicer to abort `UNAVAILABLE`.
    """
    await store.set_title(session_id, clamp_title(title))
    return RenameSessionReply()


async def delete_session(
    store: SessionStore, cascade: SessionMemoryCascade | None, session_id: str
) -> DeleteSessionReply:
    """Delete one chat and cascade to its private memories (ADR-0021 delete addendum).

    The session is hard-deleted FIRST (the visible chat is the user's primary intent), then the
    scope-aware memory cascade runs when a memory backend is wired (`cascade is None` when memory
    is off, so nothing to forget). Ordering session-first means a memory failure leaves the chat
    gone (intent satisfied) with a self-healing retry cleaning the memories, rather than a visible
    chat whose memories vanished. Both steps are idempotent, so a retry after any failure is safe.
    A `SessionStoreError` or `MemoryStoreError` propagates for the servicer to abort `UNAVAILABLE`
    (the session-read precedent).
    """
    await store.delete(session_id)
    if cascade is not None:
        await cascade.delete_session_memories(session_id)
    return DeleteSessionReply()
