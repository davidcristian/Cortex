"""RedisSessionStore: the SessionStore port over one Redis list per session."""

from collections.abc import Awaitable, Callable, Sequence
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
from cortex_session.retry import (
    DEFAULT_STORE_RETRY,
    MonotonicTimer,
    RetryTimer,
    StoreRetry,
    with_retry,
)
from cortex_session.store_codec import (
    decode_message,
    decode_recap,
    encode_message,
    encode_recap,
    messages_key,
    recap_key,
    refuse_images,
    refuse_system,
    refuse_tool_steps,
    title_key,
)

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

# A connect to a stopping container can stall instead of being refused; redis-py waits 5 s for
# one, which would spend the whole retry budget on a single try.
CONNECT_TIMEOUT_S = 1.0

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


async def append_once(client: Redis, session_id: str, record: str, score: float) -> None:
    """RPUSH ``record`` and ZADD the session in one transaction, unless the list holds it."""
    key = messages_key(session_id)
    async with client.pipeline(transaction=True) as pipe:
        await pipe.watch(key)
        if await pipe.lpos(key, record) is not None:
            return
        pipe.multi()
        pipe.rpush(key, record)
        pipe.zadd(_SESSIONS_KEY, {session_id: score})
        await pipe.execute()


class RedisSessionStore:
    """SessionStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(
        self,
        client: Redis,
        *,
        retry: StoreRetry = DEFAULT_STORE_RETRY,
        timer: RetryTimer | None = None,
    ) -> None:
        self._client = client
        self._hoisted_moved = False
        self._retry = retry
        self._timer = timer if timer is not None else MonotonicTimer()

    async def _call[T](self, call: Callable[[], Awaitable[T]], failure: str) -> T:
        """Run ``call`` under the retry, raising ``SessionStoreError(failure)`` when it fails."""
        try:
            return await with_retry(call, self._retry, self._timer)
        except RedisError as err:
            raise SessionStoreError(failure) from err

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisSessionStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        client = Redis.from_url(url, socket_connect_timeout=CONNECT_TIMEOUT_S)  # pyright: ignore[reportUnknownMemberType]
        return cls(client)

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise SessionStoreError(msg) from err

    async def append(self, session_id: str, message: Message) -> None:
        """Persist one message once and refresh the session's recency-index score."""
        refuse_images(message)
        refuse_system(message)
        refuse_tool_steps(message)
        record, score = encode_message(message), message.at.timestamp()
        await self._call(
            lambda: append_once(self._client, session_id, record, score),
            f"append to session {session_id!r} failed",
        )

    async def history(self, session_id: str) -> Sequence[Message]:
        """Return the session's full history in append order (empty when unknown)."""
        raw = await self._call(
            lambda: self._client.lrange(messages_key(session_id), 0, -1),
            f"history read for session {session_id!r} failed",
        )
        return tuple(decode_message(item, index) for index, item in enumerate(raw))

    async def set_title(self, session_id: str, title: str) -> None:
        """Persist a brain-generated display title under the session's title key."""
        await self._call(
            lambda: self._client.set(title_key(session_id), title),
            f"setting the title for session {session_id!r} failed",
        )

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        """Persist the summarizing window's recap of this session's dropped prefix."""
        await self._call(
            lambda: self._client.set(recap_key(session_id), encode_recap(recap)),
            f"setting the recap for session {session_id!r} failed",
        )

    async def recap(self, session_id: str) -> HistoryRecap | None:
        """The stored recap, or ``None`` for a session that has never had one written."""
        raw = await self._call(
            lambda: self._client.get(recap_key(session_id)),
            f"recap read for session {session_id!r} failed",
        )
        # Decoding is outside the retried read so a corrupt document is reported as corrupt rather
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

        async def delete_all() -> None:
            await self._move_old_hoisted()
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.delete(messages_key(session_id))
                pipe.delete(title_key(session_id))
                pipe.delete(recap_key(session_id))
                pipe.zrem(_SESSIONS_KEY, session_id)
                pipe.srem(_HOISTED_KEY, session_id)
                await pipe.execute()

        await self._call(delete_all, f"deleting session {session_id!r} failed")

    async def set_hoisted(self, session_id: str, *, hoisted: bool) -> None:
        """Add the chat to the hoisted set, or remove it from it."""

        async def write() -> None:
            await self._move_old_hoisted()
            if hoisted:
                await self._client.sadd(_HOISTED_KEY, session_id)
            else:
                await self._client.srem(_HOISTED_KEY, session_id)

        await self._call(write, f"hoisting or lowering session {session_id!r} failed")

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return the newest ``limit`` chats plus every hoisted chat, the hoisted ones first."""

        async def read() -> tuple[list[str], set[str], list[object]]:
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
            return ids, hoisted_ids, reads

        ids, hoisted_ids, reads = await self._call(read, "listing sessions failed")
        # Decoding is outside the retried read so a corrupt record keeps the error decode_message
        # already raised instead of being reported as a listing failure.
        summaries = (
            _summarize_ends(session_id, reads, at, hoisted=session_id in hoisted_ids)
            for at, session_id in enumerate(ids)
        )
        return merge_hoisted(summary for summary in summaries if summary is not None)
