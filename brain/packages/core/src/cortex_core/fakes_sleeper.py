"""The ``Sleeper`` port's two implementations: the real wait, and the twin that records one."""

import asyncio


class AsyncioSleeper:
    """Sleeper backed by ``asyncio.sleep``: the core's only wall-clock wait."""

    async def sleep(self, seconds: float) -> None:
        """Suspend the caller for ``seconds``, letting the rest of the loop run."""
        await asyncio.sleep(seconds)


class RecordingSleeper:
    """Sleeper twin that yields instead of waiting, recording what was asked for."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def sleep(self, seconds: float) -> None:
        """Record the requested wait and yield the loop once, consuming no time."""
        self.waits.append(seconds)
        await asyncio.sleep(0)
