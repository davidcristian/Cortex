"""RedisSessionStore: the SessionStore port over one Redis list per session.

Key layout is ``cortex:session:{session_id}:messages``, with RPUSH on append, LRANGE 0..-1
on a history read (and a bounded two-ended read for a listing, see ``list_sessions``),
one JSON document per message with an ISO-8601 timestamp. A recency ZSET (``cortex:sessions``)
and a pinned SET (``cortex:sessions:pinned``) index the catalog: a listing reads both, unions
them, and returns pinned chats regardless of recency (ADR-0021 pinning addendum). A session's
summarizing recap (ADR-0038 decision 9) sits under a key of its own beside them and is removed
with the rest on delete. The keys and both record codecs live in ``store_codec.py``, which owns
the storage format; this module owns the round trips and the error wrapping. Redis is the hot
state that survives
orchestrator restarts and model swaps (the one hard rule); this adapter only
translates. It holds no business logic, and every backend failure crosses the port as
``SessionStoreError`` with the cause chained.
"""

from collections.abc import Sequence
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import (
    HistoryRecap,
    Message,
    SessionStoreError,
    SessionSummary,
    merge_pinned,
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

# The dictated connection default; deployments override via CORTEX_REDIS_URL, which is
# read by the composition root (the orchestrator's settings), never by this adapter.
DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"

# The recency index for `list_sessions` (ADR-0021): a sorted set of session ids scored
# by last-activity unix time, maintained on `append` alongside the per-session list.
_SESSIONS_KEY = "cortex:sessions"

# The pinned set for `list_sessions` (ADR-0021 pinning addendum): the session ids the user
# pinned. A listing unions these with the recency window so a pinned chat lists even after it
# ages out of the top-N by recency; `set_pinned` maintains it and `delete` clears its member.
_PINNED_KEY = "cortex:sessions:pinned"

# What one listed session costs `list_sessions`: its first record, its last record, its
# length (the tail's index, so a corrupt tail is still named precisely), and its stored
# title (a brain-generated override, or absent for the first-message derivation).
_ENDS_READS = 4


def _summarize_ends(
    session_id: str, reads: Sequence[object], at: int, *, pinned: bool
) -> SessionSummary | None:
    """Summarize the session listed at ``at`` from the batched ends read (None when gone).

    ``reads`` is the flat pipeline result: ``_ENDS_READS`` entries per listed session, in
    the order the reads were queued (head, tail, length, title). An empty head is a dangling
    index entry (the message list is gone), the one case a listing skips instead of failing.
    A stored title (``None`` when unset) overrides the first-message derivation (ADR-0021).
    ``pinned`` (membership of the pinned set, read once for the whole listing) rides onto the
    summary and drives the pinned-first ordering (ADR-0021 pinning addendum).
    """
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
        pinned=pinned,
    )


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
        """Persist one message and refresh the session's recency-index score (ADR-0021).

        Refuses an image-bearing message outright (ADR-0029): pixels are turn-local, and the
        record schema has no field for them, so accepting one would silently drop the picture
        rather than store it. Raising is the loud half of that invariant; ``Message`` itself
        already refuses images on any role but ``TOOL``, so this is what catches a caller that
        reached the store with a TOOL message.
        """
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
        """Persist a brain-generated display title under the session's title key (ADR-0021).

        A plain string value (its own key, never a message record), so it carries no schema
        markers and `list_sessions` prefers it over the first-message derivation; a later call
        overwrites it. Not conversation content, but stored beside it so it survives a swap.
        """
        try:
            await self._client.set(title_key(session_id), title)
        except RedisError as err:
            msg = f"setting the title for session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def set_recap(self, session_id: str, recap: HistoryRecap) -> None:
        """Persist the summarizing window's recap of this session's dropped prefix.

        One JSON document under the session's own recap key, overwritten whenever the window's
        boundary moves forward. Derived state rather than something the user wrote, but stored
        beside the conversation so it survives a model swap and a restart like the rest.
        """
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
        # Decoding sits outside the wrapping above so a corrupt document is named as such
        # rather than relabelled as a read failure, exactly as `history` treats a record.
        return None if raw is None else decode_recap(cast("bytes", raw), session_id)

    async def delete(self, session_id: str) -> None:
        """Hard-delete a whole session: its messages, its title, its recap, its recency entry.

        The destructive "forget this chat" write (ADR-0021 delete addendum). Every key `append`,
        `set_title` and `set_recap` can create for this id is removed in one transaction so a
        listing never sees a half-deleted chat: the message list (`:messages`), the optional title
        (`:title`), the optional recap (`:recap`, a model-written account of the same conversation
        and so exactly as private as the transcript, ADR-0038 decision 9),
        and the `cortex:sessions` recency-index member. Nothing is left orphaned, and no dangling
        index entry remains to be skipped later. `DEL`/`ZREM` on absent keys/members are no-ops,
        so deleting an unknown or already-deleted session is idempotent, and the next `history`
        read of it is the benign empty history an unknown session already returns (no tombstone).
        """
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.delete(messages_key(session_id))
                pipe.delete(title_key(session_id))
                pipe.delete(recap_key(session_id))
                pipe.zrem(_SESSIONS_KEY, session_id)
                pipe.srem(_PINNED_KEY, session_id)
                await pipe.execute()
        except RedisError as err:
            msg = f"deleting session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def set_pinned(self, session_id: str, *, pinned: bool) -> None:
        """Pin or unpin a chat by toggling its membership in the pinned set (pinning addendum).

        `SADD` when pinning, `SREM` when unpinning, both idempotent by value, so setting the same
        state twice is a no-op. Not conversation content but stored beside it so a pin survives a
        swap. A pin on an unknown or already-deleted id is benign: the id becomes a pinned member
        with no message list, which `list_sessions` skips like any dangling index entry.
        """
        try:
            if pinned:
                await self._client.sadd(_PINNED_KEY, session_id)
            else:
                await self._client.srem(_PINNED_KEY, session_id)
        except RedisError as err:
            msg = f"setting the pin for session {session_id!r} failed"
            raise SessionStoreError(msg) from err

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        """Return the newest ``limit`` chats unioned with every pinned chat, pinned-first.

        Round trip one reads BOTH indexes in one transaction: the recency ZSET newest-first
        (capped at ``limit``) and the pinned SET. Their union is the listed set, so a pinned chat
        OLDER than the recency window still lists (the point of pinning); a chat both pinned and
        inside the window appears once (the union deduplicates ids before any fetch). Round trip two
        fetches only what a summary is derived from: each listed session's FIRST and LAST record,
        its length, and its title, batched into one transaction. So the whole list still costs two
        round trips and decodes two records per chat. `merge_pinned` then orders the union
        pinned-first, recency-descending within each group (ADR-0021 pinning addendum).

        The listed count is the window size plus the pinned chats outside it, so a heavily-pinned
        catalog lists more than ``limit``; the pinned set is small by construction (a user pins a
        handful), so the extra fetch is cheap. A session id whose list is empty (a dangling index
        entry, e.g. a pin on a since-deleted id) is skipped rather than crashing the whole list.
        Because the middle is never read, one corrupt record between the ends no longer takes the
        chat list down with it; `history` still fails loudly on it (bounded-reads addendum).
        """
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                # zrevrange's return type is a partially-Any union (scores/without-scores
                # overloads); this no-scores call yields members, cast to bytes below.
                pipe.zrevrange(_SESSIONS_KEY, 0, limit - 1)  # pyright: ignore[reportUnknownMemberType]
                pipe.smembers(_PINNED_KEY)
                recency_raw, pinned_raw = await pipe.execute()
            # Members come back as bytes (this client leaves decode_responses off, as the
            # message reads rely on); the casts pin that so decoding needs no type branch.
            recency_ids = [raw.decode("utf-8") for raw in cast("list[bytes]", recency_raw)]
            pinned_ids = {raw.decode("utf-8") for raw in cast("set[bytes]", pinned_raw)}
            # The union: the recency window, then every pinned chat outside it (sorted for a
            # deterministic fetch order; `merge_pinned` re-sorts, so the order only pins the index).
            ids = recency_ids + sorted(pinned_ids - set(recency_ids))
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
        # Decoding sits outside the wrapping above: a corrupt record is a SessionStoreError
        # already, named by _decode, and must not be relabelled as a listing failure.
        summaries = (
            _summarize_ends(session_id, reads, at, pinned=session_id in pinned_ids)
            for at, session_id in enumerate(ids)
        )
        return merge_pinned(summary for summary in summaries if summary is not None)
