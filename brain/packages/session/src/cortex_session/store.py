"""RedisSessionStore: the SessionStore port over one Redis list per session.

Key layout is ``cortex:session:{session_id}:messages``, with RPUSH on append, LRANGE 0..-1
on a history read (and a bounded two-ended read for a listing, see ``list_sessions``),
one JSON document per message with an ISO-8601 timestamp. Records carry
``"v"``/``"kind"`` as the schema escape hatch; the read policy (see ``_decode``) is:
unknown EXTRA keys are ignored (forward-compatible additions), an unknown kind or
unsupported version fails LOUDLY naming the record and is never a silent skip, which would
invisibly corrupt a future handoff's context. Redis is the hot state that survives
orchestrator restarts and model swaps (the one hard rule); this adapter only
translates. It holds no business logic, and every backend failure crosses the port as
``SessionStoreError`` with the cause chained.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import (
    Message,
    Role,
    SessionStoreError,
    SessionSummary,
    summarize_ends,
)

# The dictated connection default; deployments override via CORTEX_REDIS_URL, which is
# read by the composition root (the orchestrator's settings), never by this adapter.
DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

# The recency index for `list_sessions` (ADR-0021): a sorted set of session ids scored
# by last-activity unix time, maintained on `append` alongside the per-session list.
_SESSIONS_KEY = "cortex:sessions"

# What one listed session costs `list_sessions`: its first record, its last record, and
# its length (the tail's index, so a corrupt tail is still named precisely).
_ENDS_READS = 3

# The record schema this writer emits and the ONLY combination this reader accepts.
# Records missing the markers decode as this combination (pre-versioning writers).
_RECORD_KIND = "message"
_RECORD_VERSION = 1


def _key(session_id: str) -> str:
    return f"cortex:session:{session_id}:messages"


def _encode(message: Message) -> str:
    return json.dumps(
        {
            "v": _RECORD_VERSION,
            "kind": _RECORD_KIND,
            "role": message.role.value,
            "text": message.text,
            "at": message.at.isoformat(),
            "turn_id": message.turn_id,
        }
    )


def _decode(raw: bytes | str, index: int) -> Message:
    """Decode the record at ``index``; every failure names that record precisely.

    Only the known keys are read, so unknown extra keys pass through untouched; an
    unknown kind/version raises BEFORE field decoding so future record shapes fail
    with the precise message, not as an arbitrary missing-field error.
    """
    try:
        fields = cast("dict[str, str]", json.loads(raw))
        kind = fields.get("kind", _RECORD_KIND)
        version = fields.get("v", _RECORD_VERSION)
        if kind != _RECORD_KIND or version != _RECORD_VERSION:
            msg = (
                f"unreadable session record at index {index}: kind {kind!r} v {version!r}"
                f" (this reader supports kind {_RECORD_KIND!r} v {_RECORD_VERSION})"
            )
            raise SessionStoreError(msg)
        return Message(
            role=Role(fields["role"]),
            text=fields["text"],
            at=datetime.fromisoformat(fields["at"]),
            turn_id=fields["turn_id"],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        # AttributeError: a JSON document that is not an object has no .get.
        msg = f"corrupt session record at index {index}"
        raise SessionStoreError(msg) from err


def _summarize_ends(session_id: str, reads: Sequence[object], at: int) -> SessionSummary | None:
    """Summarize the session listed at ``at`` from the batched ends read (None when gone).

    ``reads`` is the flat pipeline result: ``_ENDS_READS`` entries per listed session, in
    the order the reads were queued. An empty head is a dangling index entry (the message
    list is gone), the one case a listing skips instead of failing.
    """
    base = at * _ENDS_READS
    head = cast("list[bytes]", reads[base])
    tail = cast("list[bytes]", reads[base + 1])
    length = cast("int", reads[base + 2])
    if not head:
        return None
    return summarize_ends(session_id, _decode(head[0], 0), _decode(tail[0], length - 1))


class RedisSessionStore:
    """SessionStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisSessionStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        # redis-py types from_url's **kwargs as Unknown; this call passes none of them.
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise SessionStoreError(msg) from err

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message and refresh the session's recency-index score (ADR-0021)."""
        try:
            await self._client.rpush(_key(session_id), _encode(message))
            await self._client.zadd(_SESSIONS_KEY, {session_id: message.at.timestamp()})
        except RedisError as err:
            msg = f"append to session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        try:
            raw = await self._client.lrange(_key(session_id), 0, -1)
        except RedisError as err:
            msg = f"history read for session {session_id!r} failed"
            raise SessionStoreError(msg) from err
        return tuple(_decode(item, index) for index, item in enumerate(raw))

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return at most ``limit`` recent chats, most-recently-active first (ADR-0021).

        Reads the recency index newest-first, then fetches only what a summary is derived
        from: each listed session's FIRST and LAST record plus its length, every listed
        session's three reads batched into one transaction. So the whole list costs two
        round trips (index, then ends) and decodes two records per chat, not one round trip
        per chat each decoding a whole history. The length is read with the pair (and
        atomically with it) so a corrupt tail record still names its true index.

        A session id whose list is empty (a dangling index entry, e.g. after a future
        deletion) is skipped rather than crashing the whole list. Because the middle is
        never read, one corrupt record between the ends no longer takes the chat list down
        with it; `history` still fails loudly on it, so the context a turn is built from
        keeps its fail-loud guarantee (ADR-0021 bounded-reads addendum).
        """
        try:
            # zrevrange's return type is a partially-Any union (scores/without-scores
            # overloads); this no-scores call yields members, cast to bytes below.
            raw_ids = await self._client.zrevrange(  # pyright: ignore[reportUnknownMemberType]
                _SESSIONS_KEY, 0, limit - 1
            )
            # Members come back as bytes (this client leaves decode_responses off, as the
            # message reads rely on); the cast pins that so decoding needs no type branch.
            ids = [raw_id.decode("utf-8") for raw_id in cast("list[bytes]", raw_ids)]
            async with self._client.pipeline(transaction=True) as pipe:
                for session_id in ids:
                    key = _key(session_id)
                    pipe.lrange(key, 0, 0)
                    pipe.lrange(key, -1, -1)
                    pipe.llen(key)
                reads = await pipe.execute()
        except RedisError as err:
            msg = "listing sessions failed"
            raise SessionStoreError(msg) from err
        # Decoding sits outside the wrapping above: a corrupt record is a SessionStoreError
        # already, named by _decode, and must not be relabelled as a listing failure.
        summaries = (_summarize_ends(session_id, reads, at) for at, session_id in enumerate(ids))
        return tuple(summary for summary in summaries if summary is not None)
