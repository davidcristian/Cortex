"""The loop that keeps retrying a tier the standing residency is missing (ADR-0030 decision 4).

Split from ``residency_tiers.py`` along the same seam the rest of this family is split on: that
module owns the record and what one retry pass does, this owns *when* a pass happens and who
owns the task it runs in. Deliberately generic about the pass itself, taking a coroutine factory
rather than the manager, so the object that knows whether a handoff is in flight keeps that
judgement (``SwappingModelManager.heal_standing_tiers``) and nothing here has to import it.

The loop owns its own task, unlike the schedule ticker's, whose start and stop are two more lines
at a composition root already at its line cap. The lifecycle is the same otherwise: an
unenumerated bug in a pass degrades to a skipped pass rather than a silently dead loop, a stop is
a signal rather than a cancellation so an in-flight pass finishes, and the wait between passes
wakes early on that signal instead of holding shutdown for the interval.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

# How long between two retry passes. A missing tier costs the pool its whole GPU allowance, so
# the wait is short next to the minutes a tier takes to load, and it is spent on two control
# calls to a loopback sidecar only while something is actually broken: a record with nothing in
# it makes a pass that asks nobody anything. The deployment overrides it with
# CORTEX_SWAP_TIER_HEAL_S.
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
        """Signal the loop and wait out the in-flight pass; a loop never started is a no-op.

        No forced cancel and no grace bound, unlike the ticker's stop: a pass is at most two
        control calls, each already bounded by the model host client's own deadline, so the wait
        cannot outlast what the deployment configured that client to spend.
        """
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
