"""The background reading of whether every part a turn needs answers, for ``Health`` to state."""

import asyncio
import contextlib
import logging
from collections.abc import Sequence

from cortex_core.ports_models import ServingProbe

# The overlay asks again every 5 s while its dot is not green, so a reading is at most one
# interval older than that. A pass is one Redis PING and one HTTP GET on the local network.
SERVING_CHECK_INTERVAL_S = 2.0

# Under the interval, so a pass ends before the next one is due.
SERVING_CHECK_TIMEOUT_S = 1.0

_logger = logging.getLogger(__name__)


class ServingWatch:
    """Asks every probe each ``interval_s`` seconds and keeps the first fault for a plain read."""

    def __init__(
        self,
        probes: Sequence[ServingProbe],
        *,
        interval_s: float = SERVING_CHECK_INTERVAL_S,
        timeout_s: float = SERVING_CHECK_TIMEOUT_S,
    ) -> None:
        self._probes = tuple(probes)
        self._interval_s = interval_s
        self._timeout_s = timeout_s
        self._fault: str | None = None
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def fault(self) -> str | None:
        """The first fault in probe order from the last pass, or ``None`` when all answered."""
        return self._fault

    async def refresh(self) -> None:
        """Ask every probe at once, each within ``timeout_s``, and keep what they said."""
        faults = await asyncio.gather(*(self._ask(probe) for probe in self._probes))
        fault = next((each for each in faults if each is not None), None)
        if fault != self._fault:
            if fault is None:
                _logger.info("every part a turn needs is answering again")
            else:
                _logger.warning("a part a turn needs is not answering", extra={"fault": fault})
        self._fault = fault

    async def start(self) -> None:
        """Take the first reading, then refresh it in a task of its own until ``aclose``."""
        if self._task is None:
            await self.refresh()
            self._task = asyncio.create_task(self._run(), name="serving-watch")

    async def aclose(self) -> None:
        """Stop the loop and wait out a pass in flight; a watch never started is a no-op."""
        self._stopping.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval_s)
            if self._stopping.is_set():
                return
            try:
                await self.refresh()
            except Exception:
                _logger.exception("a serving check failed; the next pass asks again")

    async def _ask(self, probe: ServingProbe) -> str | None:
        try:
            async with asyncio.timeout(self._timeout_s):
                return await probe.fault()
        except TimeoutError:
            return f"{probe.part} did not answer within {self._timeout_s:g} s"
