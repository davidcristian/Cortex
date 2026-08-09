"""The loop that keeps retrying a tier the standing residency is missing (ADR-0030 decision 4)."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

DEFAULT_TIER_HEAL_INTERVAL_S = 30.0

_logger = logging.getLogger(__name__)


class TierHealer:
    """Runs one retry pass every ``interval_s`` seconds, in a task it starts and stops itself."""

    def __init__(
        self,
        heal: Callable[[], Awaitable[None]],
        *,
        interval_s: float = DEFAULT_TIER_HEAL_INTERVAL_S,
    ) -> None:
        self._heal = heal
        self._interval_s = interval_s
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Begin looping beside the seam. Idempotent: a second call keeps the first task."""
        if self._task is None:
            self._task = asyncio.create_task(self.run(), name="residency-tier-healer")

    async def aclose(self) -> None:
        """Signal the loop and wait out the in-flight pass; a loop never started is a no-op."""
        self._stopping.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def run(self) -> None:
        """Retry until stopped; a failing pass is logged and retried at the next interval."""
        while not self._stopping.is_set():
            try:
                await self._heal()
            except Exception:
                # The same pass guard the schedule ticker keeps: a bug nobody enumerated must
                # cost one pass, never the retrying that a degraded stack is waiting on.
                _logger.exception("a residency tier retry failed; the next pass tries again")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_s)
