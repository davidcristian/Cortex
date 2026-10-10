"""``ServingProbe`` over the Redis the conversation store calls."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

STORE_PART = "the conversation store"
STORE_DOWN = "the conversation store is not answering, so a turn cannot be saved"


class RedisPing:
    """Sends Redis one PING per check, over a client it shares and does not close."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @property
    def part(self) -> str:
        """The part this probe asks about."""
        return STORE_PART

    async def fault(self) -> str | None:
        """``None`` when Redis answers the PING, and the store's fault when it does not."""
        try:
            await self._client.ping()  # pyright: ignore[reportUnknownMemberType]
        except RedisError:
            return STORE_DOWN
        return None
