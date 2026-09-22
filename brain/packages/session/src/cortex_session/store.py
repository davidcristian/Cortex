"""RedisSessionStore: the SessionStore port over one Redis list per session."""

from collections.abc import Sequence
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import (
    HistoryRecap,
    Message,
    SessionStoreError,
    SessionSummary,
    merge_hoisted,
    summarize_ends,
)
from cortex_session.store_codec import (
    decode_message,
    decode_recap,
    encode_message,
    encode_recap,
    messages_key,
    recap_key,
    refuse_images,
    title_key,
)

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

_SESSIONS_KEY = "cortex:sessions"

_HOISTED_KEY = "cortex:sessions:hoisted"

# A store written before the feature was named Hoist keeps its hoisted ids under this key.
_OLD_HOISTED_KEY = "cortex:sessions:pinned"

# Reads queued per listed session, in this order: head, tail, length, title.
_ENDS_READS = 4


def _summarize_ends(
    session_id: str, reads: Sequence[object], at: int, *, hoisted: bool
) -> SessionSummary | None:
    """Summarize the session listed at ``at`` from the batched ends read (None when gone)."""
    base = at * _ENDS_READS
    head = cast("list[bytes]", reads[base])
    tail = cast("list[bytes]", reads[base + 1])
    length = cast("int", reads[base + 2])
    raw_title = reads[base + 3]
    if not head:
        return None
    title = cast("bytes", raw_title).decode("utf-8") if raw_title is not None else None
    return summarize_ends(
        session_id,
        decode_message(head[0], 0),
        decode_message(tail[0], length - 1),
        title_override=title,
        hoisted=hoisted,
    )


class RedisSessionStore:
    """SessionStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._hoisted_moved = False

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisSessionStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise SessionStoreError(msg) from err

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message and refresh the session's recency-index score."""
        refuse_images(message)
        try:
            await self._client.rpush(messages_key(session_id), encode_message(message))
            await self._client.zadd(_SESSIONS_KEY, {session_id: message.at.timestamp()})
        except RedisError as err:
            msg = f"append to session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        try:
            raw = await self._client.lrange(messages_key(session_id), 0, -1)
        except RedisError as err:
            msg = f"history read for session {session_id!r} failed"
            raise SessionStoreError(msg) from err
        return tuple(decode_message(item, index) for index, item in enumerate(raw))

    async def set_title(self, session_id: str, title: str) -> None:
        """Persist a brain-generated display title under the session's title key."""
        try:
            await self._client.set(title_key(session_id), title)
        except RedisError as err:
            msg = f"setting the title for session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        """Persist the summarizing window's recap of this session's dropped prefix."""
        try:
            await self._client.set(recap_key(session_id), encode_recap(recap))
        except RedisError as err:
            msg = f"setting the recap for session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def recap(self, session_id: str) -> HistoryRecap | None:
        """The stored recap, or ``None`` for a session that has never had one written."""
        try:
            raw = await self._client.get(recap_key(session_id))
        except RedisError as err:
            msg = f"recap read for session {session_id!r} failed"
            raise SessionStoreError(msg) from err
        # Decoding is outside the try above so a corrupt document is reported as corrupt rather
        # than as a read failure.
        return None if raw is None else decode_recap(cast("bytes", raw), session_id)

    async def _move_old_hoisted(self) -> None:
        """Move the ids under the old key into the hoisted set, once per store (idempotent)."""
        if self._hoisted_moved:
            return
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.sunionstore(_HOISTED_KEY, [_HOISTED_KEY, _OLD_HOISTED_KEY])  # pyright: ignore[reportUnknownMemberType]
            pipe.delete(_OLD_HOISTED_KEY)
            await pipe.execute()
        self._hoisted_moved = True

    async def delete(self, session_id: str) -> None:
        """Hard-delete a whole session: its messages, its title, its recap, its recency entry."""
        try:
            await self._move_old_hoisted()
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.delete(messages_key(session_id))
                pipe.delete(title_key(session_id))
                pipe.delete(recap_key(session_id))
                pipe.zrem(_SESSIONS_KEY, session_id)
                pipe.srem(_HOISTED_KEY, session_id)
                await pipe.execute()
        except RedisError as err:
            msg = f"deleting session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def set_hoisted(self, session_id: str, *, hoisted: bool) -> None:
        """Add the chat to the hoisted set, or remove it from it."""
        try:
            await self._move_old_hoisted()
            if hoisted:
                await self._client.sadd(_HOISTED_KEY, session_id)
            else:
                await self._client.srem(_HOISTED_KEY, session_id)
        except RedisError as err:
            msg = f"hoisting or lowering session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return the newest ``limit`` chats plus every hoisted chat, the hoisted ones first."""
        try:
            await self._move_old_hoisted()
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zrevrange(_SESSIONS_KEY, 0, limit - 1)  # pyright: ignore[reportUnknownMemberType]
                pipe.smembers(_HOISTED_KEY)
                recency_raw, hoisted_raw = await pipe.execute()
            recency_ids = [raw.decode("utf-8") for raw in cast("list[bytes]", recency_raw)]
            hoisted_ids = {raw.decode("utf-8") for raw in cast("set[bytes]", hoisted_raw)}
            ids = recency_ids + sorted(hoisted_ids - set(recency_ids))
            async with self._client.pipeline(transaction=True) as pipe:
                for session_id in ids:
                    key = messages_key(session_id)
                    pipe.lrange(key, 0, 0)
                    pipe.lrange(key, -1, -1)
                    pipe.llen(key)
                    pipe.get(title_key(session_id))
                reads = await pipe.execute()
        except RedisError as err:
            msg = "listing sessions failed"
            raise SessionStoreError(msg) from err
        # Decoding is outside the try above so a corrupt record keeps the error decode_message
        # already raised instead of being reported as a listing failure.
        summaries = (
            _summarize_ends(session_id, reads, at, hoisted=session_id in hoisted_ids)
            for at, session_id in enumerate(ids)
        )
        return merge_hoisted(summary for summary in summaries if summary is not None)
