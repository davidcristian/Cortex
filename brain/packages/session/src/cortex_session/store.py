"""RedisSessionStore: the SessionStore port over one Redis list per session.

Key layout is ``cortex:session:{session_id}:messages``, with RPUSH on append, LRANGE 0..-1
on read, one JSON document per message with an ISO-8601 timestamp. Records carry
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
    summarize_session,
)

# The dictated connection default; deployments override via CORTEX_REDIS_URL, which is
# read by the composition root (the orchestrator's settings), never by this adapter.
DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

# The recency index for `list_sessions` (ADR-0021): a sorted set of session ids scored
# by last-activity unix time, maintained on `append` alongside the per-session list.
_SESSIONS_KEY = "cortex:sessions"

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

        Reads the recency index newest-first, then loads each session's history (reusing
        `history`, so its decode + error wrapping apply) and derives the summary in the
        core. A session id whose list is empty (a dangling index entry, e.g. after a
        future deletion) is skipped rather than crashing the whole list.
        """
        try:
            # zrevrange's return type is a partially-Any union (scores/without-scores
            # overloads); this no-scores call yields members, cast to bytes below.
            raw_ids = await self._client.zrevrange(  # pyright: ignore[reportUnknownMemberType]
                _SESSIONS_KEY, 0, limit - 1
            )
        except RedisError as err:
            msg = "listing sessions failed"
            raise SessionStoreError(msg) from err
        # Members come back as bytes (this client leaves decode_responses off, as the
        # message reads below rely on); the cast pins that so decoding needs no type branch.
        ids = cast("list[bytes]", raw_ids)
        summaries: list[SessionSummary] = []
        for raw_id in ids:
            session_id = raw_id.decode("utf-8")
            messages = await self.history(session_id)
            if messages:
                summaries.append(summarize_session(session_id, messages))
        return tuple(summaries)
