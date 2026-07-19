"""RedisPreferenceStore: the PreferenceStore port over one Redis hash."""

from collections.abc import Mapping

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import PreferenceStoreError
from cortex_session.store import DEFAULT_REDIS_URL

_PREFERENCES_KEY = "cortex:preferences"


class RedisPreferenceStore:
    """PreferenceStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisPreferenceStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise PreferenceStoreError(msg) from err

    async def all(self) -> Mapping[str, str]:
        """Every stored pair in one HGETALL; an unset record is an empty mapping, never an error."""
        try:
            raw = await self._client.hgetall(_PREFERENCES_KEY)
        except RedisError as err:
            msg = "reading the preferences failed"
            raise PreferenceStoreError(msg) from err
        return {_text(key): _text(value) for key, value in raw.items()}

    async def set(self, key: str, value: str) -> None:
        """Write one field, or delete it when ``value`` is empty (the port's clear convention)."""
        try:
            if value == "":
                await self._client.hdel(_PREFERENCES_KEY, key)
                return
            await self._client.hset(_PREFERENCES_KEY, key, value)
        except RedisError as err:
            msg = f"setting the preference {key!r} failed"
            raise PreferenceStoreError(msg) from err


def _text(value: bytes | str) -> str:
    """Decode one hash field or value; redis-py returns bytes unless decoding is configured."""
    return value.decode() if isinstance(value, bytes) else value
