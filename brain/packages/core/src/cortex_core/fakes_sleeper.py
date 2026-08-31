"""The ``Sleeper`` port's two implementations: the real wait, and the twin that records one.

``AsyncioSleeper`` is production wiring, not a stub (the ``SystemClock`` precedent in
``fakes.py``): it is the thin adapter that lets the core wait without importing ``asyncio``
itself. ``RecordingSleeper`` is its twin for tests and CI: it records every requested wait and
yields the event loop instead of consuming time, which is what keeps the swap suite's readiness
gate and its timeout path free of wall-clock sleeps while still exercising the real loop.
"""

import asyncio


class AsyncioSleeper:
    """Sleeper backed by ``asyncio.sleep``: the core's only wall-clock wait (ADR-0030)."""

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for ``seconds``, letting the rest of the loop run."""
        await asyncio.sleep(seconds)


class RecordingSleeper:
    """Sleeper twin that yields instead of waiting, recording what was asked for.

    ``waits`` holds every requested duration in order, so a test asserts the schedule a poll
    loop asked for rather than measuring elapsed time (the body's ``FakeSleeper`` discipline).
    Each call still yields the loop once, so a bounded poll loop makes progress and any deadline
    the caller measures off its ``Clock`` is reached in scheduling order, never in real time.
    """

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def sleep(self, seconds: float) -> None:
        """Record the requested wait and yield the loop once, consuming no time."""
        self.waits.append(seconds)
        await asyncio.sleep(0)
