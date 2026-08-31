"""In-memory ``SubagentScheduler`` fake: admit everything, drain like the real pool (ADR-0030).

Split out of ``fakes.py`` for the line cap (the ``fakes_body``/``fakes_handoff`` precedent).
``ResourceBudgetScheduler`` is itself pure and is what production wires; this twin exists for
composition tests (the swap conductor's chaos suite) that need admission always granted, with no
budget arithmetic to stage, while keeping the port's drain contract observable: admit raises while
draining, drain waits bounded for in-flight admissions, undrain reopens admission. It passes the
same drain contract suite as the real scheduler (``test_scheduler_drain.py``), which is what makes
it a twin rather than a stub.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.errors import SubagentAdmissionError
from cortex_core.placement import PlacementRequest
from cortex_core.scheduler import POOL_DRAINING_MSG


class AdmitAllScheduler:
    """SubagentScheduler twin with no budget: every admit is granted at once, unless draining.

    ``admitted`` records every granted request in admission order, so a composition test can
    assert what got through, and that nothing did during a drain window.
    """

    def __init__(self) -> None:
        self.admitted: list[PlacementRequest] = []
        self._in_flight = 0
        self._draining = False
        self._pool = asyncio.Condition()

    @asynccontextmanager
    async def admit(self, request: PlacementRequest) -> AsyncGenerator[None, None]:
        """Grant the request immediately; raise ``SubagentAdmissionError`` while draining."""
        async with self._pool:
            if self._draining:
                raise SubagentAdmissionError(POOL_DRAINING_MSG)
            self.admitted.append(request)
            self._in_flight += 1
        try:
            yield
        finally:
            async with self._pool:
                self._in_flight -= 1
                self._pool.notify_all()

    async def drain(self, *, timeout_s: float) -> bool:
        """Stop admitting, then wait (bounded) for in-flight admissions to release.

        Same contract as the real scheduler's: True means drained clean, False means the bound
        elapsed with work still in flight (nothing killed), and admission stays closed either
        way until ``undrain``.
        """
        async with self._pool:
            self._draining = True
            self._pool.notify_all()
            try:
                async with asyncio.timeout(timeout_s):
                    while self._in_flight > 0:
                        await self._pool.wait()
            except TimeoutError:
                return False
            return True

    def undrain(self) -> None:
        """Resume admission: the reverse of ``drain``, idempotent (an aborted swap calls it too)."""
        self._draining = False
