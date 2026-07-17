"""RedisHandoffStore: the HandoffStore port over Redis keys for the brain handoff (ADR-0030).

Key layout: ``cortex:handoff:{id}`` holds one ``HandoffRecord`` JSON document (codec in
``handoff_codec.py``), and ``cortex:handoff:active`` is the single-active-handoff pointer (one
GPU, at most one swap in flight): a non-terminal write claims it, a terminal write or a delete
of the record it names releases it, and ``active()`` follows it. Non-terminal records carry
**no TTL**, so a crash-stranded handoff is still there for boot recovery to find and mark
``FAILED``; terminal records expire after an hour (kept briefly for diagnosis, ADR-0030
decision 4). Each multi-key write runs as one transactional pipeline so a crash cannot orphan
the pointer from its record; the read-then-write verbs are not fenced against a concurrent
writer, because the conductor is the store's one writer by construction (``active()`` is how
it checks that), unlike the multi-claimant schedule store. This adapter only translates: every
backend failure crosses the port as ``HandoffStoreError`` with the cause chained, and a
corrupt record fails LOUDLY naming its key. The taint fields round-trip whole (bit, sources
order, URL set): taint that did not survive a re-read would fail open after the swap.
"""

from dataclasses import replace
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import HandoffRecord, HandoffState, HandoffStoreError
from cortex_session.handoff_codec import ACTIVE_KEY, decode_record, encode_record, record_key
from cortex_session.store import DEFAULT_REDIS_URL

# How long a terminal (DONE/FAILED) record stays readable for diagnosis before expiring.
_TERMINAL_TTL_SECONDS = 3600


def _points_at(raw: object, handoff_id: str) -> bool:
    """Whether the active pointer's raw value names ``handoff_id`` (bytes off the wire)."""
    return raw is not None and cast("bytes", raw).decode("utf-8") == handoff_id


class RedisHandoffStore:
    """HandoffStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisHandoffStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise HandoffStoreError(msg) from err

    async def put(self, record: HandoffRecord) -> None:
        """Persist one record and keep the active pointer true to its state.

        A non-terminal record is written without TTL and claims the pointer in the same
        transaction. A terminal one is written under the diagnosis TTL and releases the
        pointer when it holds this id, so a record can never be both finished and active.
        """
        encoded = encode_record(record)
        key = record_key(record.handoff_id)
        try:
            if not record.state.terminal:
                async with self._client.pipeline(transaction=True) as pipe:
                    pipe.set(key, encoded)
                    pipe.set(ACTIVE_KEY, record.handoff_id)
                    await pipe.execute()
                return
            pointer = await self._client.get(ACTIVE_KEY)
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.set(key, encoded, ex=_TERMINAL_TTL_SECONDS)
                if _points_at(pointer, record.handoff_id):
                    pipe.delete(ACTIVE_KEY)
                await pipe.execute()
        except RedisError as err:
            msg = f"put for handoff {record.handoff_id!r} failed"
            raise HandoffStoreError(msg) from err

    async def get(self, handoff_id: str) -> HandoffRecord | None:
        """Return the record with ``handoff_id``, or None when unknown/expired."""
        try:
            raw = await self._client.get(record_key(handoff_id))
        except RedisError as err:
            msg = f"get for handoff {handoff_id!r} failed"
            raise HandoffStoreError(msg) from err
        return decode_record(raw, handoff_id) if raw is not None else None

    async def transition(self, handoff_id: str, state: HandoffState) -> bool:
        """Rewrite the record's state (False for an unknown id, never an error).

        A read-modify-write through ``put``, so a terminal transition inherits its TTL and
        pointer release atomically with the state change.
        """
        record = await self.get(handoff_id)
        if record is None:
            return False
        await self.put(replace(record, state=state))
        return True

    async def delete(self, handoff_id: str) -> None:
        """Remove the record outright, idempotently, releasing the pointer if it names it."""
        try:
            pointer = await self._client.get(ACTIVE_KEY)
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.delete(record_key(handoff_id))
                if _points_at(pointer, handoff_id):
                    pipe.delete(ACTIVE_KEY)
                await pipe.execute()
        except RedisError as err:
            msg = f"delete for handoff {handoff_id!r} failed"
            raise HandoffStoreError(msg) from err

    async def active(self) -> HandoffRecord | None:
        """Return the one in-flight (non-terminal) record, or None when no handoff is live.

        Read-only self-healing: a pointer left dangling or naming a terminal record (a crash
        inside the tiny window a non-transactional writer could leave, which no verb here
        opens) reads as "no active handoff" rather than resurrecting a finished one; nothing
        is mutated on a read path.
        """
        try:
            pointer = await self._client.get(ACTIVE_KEY)
        except RedisError as err:
            msg = "reading the active handoff failed"
            raise HandoffStoreError(msg) from err
        if pointer is None:
            return None
        record = await self.get(cast("bytes", pointer).decode("utf-8"))
        if record is None or record.state.terminal:
            return None
        return record
