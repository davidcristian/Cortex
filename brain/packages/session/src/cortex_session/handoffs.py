"""RedisHandoffStore: the HandoffStore port over Redis keys for the brain handoff (ADR-0030)."""

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
        """Persist one record and keep the active pointer true to its state."""
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

    async def transition(
        self, handoff_id: str, state: HandoffState, *, failure: str | None = None
    ) -> bool:
        """Rewrite the record's state and reason (False for an unknown id, never an error)."""
        record = await self.get(handoff_id)
        if record is None:
            return False
        await self.put(replace(record, state=state, failure=failure))
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
        """Return the one in-flight (non-terminal) record, or None when no handoff is live."""
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
