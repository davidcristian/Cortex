"""RedisPreferenceStore: the PreferenceStore port over one Redis hash.

Key layout is a single hash, ``cortex:preferences``, one field per setting. A hash rather than a
key per setting because ``all`` is the common read (the overlay asks once at startup) and HGETALL
is one round trip, while the alternative is a SCAN over a keyspace this adapter would then own.
Values are opaque strings stored verbatim: this adapter never parses a preference, so a new one
costs no change here. Writing an empty value HDELs the field (the port's clear convention), so a
cleared preference is absent rather than present-and-empty, and the reader's default applies.

This is the durable half of the record: Redis persists with append-only mode and a named volume
(docker/docker-compose.yml), so a preference survives a brain restart, a Redis restart, and a
reinstall of the body that set it. The adapter only translates; every backend failure crosses the
port as ``PreferenceStoreError`` with the cause chained.
"""

from collections.abc import Mapping

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import PreferenceStoreError
from cortex_session.store import DEFAULT_REDIS_URL

# The one hash holding every setting; fields are the caller's namespaced keys.
_PREFERENCES_KEY = "cortex:preferences"


class RedisPreferenceStore:
    """PreferenceStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisPreferenceStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        # redis-py types from_url's **kwargs as Unknown; this call passes none of them.
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
    """Decode one hash field or value; redis-py answers bytes unless decoding is configured."""
    return value.decode() if isinstance(value, bytes) else value
