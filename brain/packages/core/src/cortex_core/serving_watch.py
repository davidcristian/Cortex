"""The background reading of whether every part a turn needs answers, for ``Health`` to state."""

import asyncio
import contextlib
import logging
from collections.abc import Sequence

from cortex_core.ports_models import ServingProbe
from cortex_core.residency_state import Fence

# The overlay asks again every 5 s while its dot is not green, so a reading is at most one
# interval older than that. A pass is one Redis PING and one HTTP GET on the local network.
SERVING_CHECK_INTERVAL_S = 2.0

# Under the interval, so a pass ends before the next one is due.
SERVING_CHECK_TIMEOUT_S = 1.0

_logger = logging.getLogger(__name__)


class ServingWatch:
    """Asks every probe each ``interval_s`` seconds; keeps the first fault and the notes to read."""

    def __init__(
        self,
        probes: Sequence[ServingProbe],
        *,
        noting: Sequence[ServingProbe] = (),
        interval_s: float = SERVING_CHECK_INTERVAL_S,
        timeout_s: float = SERVING_CHECK_TIMEOUT_S,
    ) -> None:
        """``probes`` are parts a turn needs; a fault from one of ``noting`` is a note instead."""
        self._probes = tuple(probes)
        self._noting = tuple(noting)
        self._interval_s = interval_s
        self._timeout_s = timeout_s
        self._fault: str | None = None
        self._notes: tuple[str, ...] = ()
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def fault(self) -> str | None:
        """The first fault in probe order from the last pass, or ``None`` when all answered."""
        return self._fault

    def notes(self) -> tuple[str, ...]:
        """Every fault the ``noting`` probes gave in the last pass, in probe order."""
        return self._notes

    async def refresh(self) -> None:
        """Ask every probe at once, each within ``timeout_s``, and keep what they said."""
        answers = await asyncio.gather(
            *(self._ask(probe) for probe in (*self._probes, *self._noting))
        )
        faults = answers[: len(self._probes)]
        fault = next((each for each in faults if each is not None), None)
        if fault != self._fault:
            if fault is None:
                _logger.info("every part a turn needs is answering again")
            else:
                _logger.warning("a part a turn needs is not answering", extra={"fault": fault})
        self._fault = fault
        notes = tuple(each for each in answers[len(self._probes) :] if each is not None)
        if notes != self._notes:
            if notes:
                _logger.warning(
                    "a server delegated work needs is not answering",
                    extra={"notes": "; ".join(notes)},
                )
            else:
                _logger.info("every server delegated work needs is answering again")
        self._notes = notes

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


class FencedServingProbe:
    """A ``ServingProbe`` whose fault counts only when no handoff held the card around the ask."""

    def __init__(self, probe: ServingProbe, between_handoffs: Fence) -> None:
        self._probe = probe
        self._between_handoffs = between_handoffs

    @property
    def part(self) -> str:
        """The part the wrapped probe asks about."""
        return self._probe.part

    async def fault(self) -> str | None:
        """The wrapped probe's answer, or ``None`` when a handoff held the card before or after."""
        # A swap stops the cortex on purpose and says so in the residency report; a reading
        # taken across one would outlive it by an interval and show a stopped cortex as down.
        if not self._between_handoffs():
            return None
        fault = await self._probe.fault()
        return fault if self._between_handoffs() else None
