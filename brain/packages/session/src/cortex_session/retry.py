"""Bounded retry for a Redis store call whose connection was refused, dropped or timed out."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from redis.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExternalAuthProviderError,
    WatchError,
)
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

_logger = logging.getLogger(__name__)

RETRY_LOG_MSG = "a Redis call failed on its connection; calling it again after a wait"

_RETRIED = (RedisConnectionError, RedisTimeoutError, WatchError)

# These subclass ``ConnectionError`` in redis-py, and no wait makes a refused credential valid.
_PERMANENT = (AuthenticationError, AuthorizationError, ExternalAuthProviderError)


class RetryTimer(Protocol):
    """The clock and the wait a retry runs on."""

    def now_ms(self) -> int: ...

    async def sleep(self, seconds: float) -> None: ...


class MonotonicTimer:
    """``RetryTimer`` over the monotonic clock and ``asyncio.sleep``."""

    def now_ms(self) -> int:
        """Milliseconds on the monotonic clock."""
        return time.monotonic_ns() // 1_000_000

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for ``seconds``."""
        await asyncio.sleep(seconds)


@dataclass(frozen=True, slots=True)
class StoreRetry:
    """How long a store call waits out a Redis that refuses, drops or stalls its connection."""

    budget_ms: int = 3000
    first_wait_ms: int = 50
    max_wait_ms: int = 1000


DEFAULT_STORE_RETRY = StoreRetry()


async def with_retry[T](
    call: Callable[[], Awaitable[T]], retry: StoreRetry, timer: RetryTimer
) -> T:
    """Return ``call()``, called again after waits that double to a cap until the budget ends.

    Only an idempotent ``call`` may be passed: a lost reply can follow a write that went through.
    """
    deadline_ms = timer.now_ms() + retry.budget_ms
    wait_ms = retry.first_wait_ms
    while True:
        try:
            return await call()
        except _RETRIED as err:
            left_ms = deadline_ms - timer.now_ms()
            if isinstance(err, _PERMANENT) or left_ms <= 0:
                raise
            pause_ms = min(wait_ms, left_ms)
            _logger.warning(RETRY_LOG_MSG, extra={"wait_ms": pause_ms, "error": type(err).__name__})
        await timer.sleep(pause_ms / 1000)
        wait_ms = min(wait_ms * 2, retry.max_wait_ms)
