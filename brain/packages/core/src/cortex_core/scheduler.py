"""ResourceBudgetScheduler: a pure soft CPU/RAM admission budget (asyncio, no I/O, see ADR-0012)."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.errors import SubagentAdmissionError
from cortex_core.placement import PlacementRequest

POOL_DRAINING_MSG = "pool draining for a model handoff; delegation resumes when the handoff ends"

ADMISSION_WAIT_MSG = (
    "waited {timeout_s:g}s for room in the subagent budget and it never came; the work queued "
    "ahead of this spawn outlasts the deployment's admission bound, so spawning it again now "
    "would join the back of the same queue"
)

DEFAULT_ADMISSION_WAIT_S = 3600.0


class ResourceBudgetScheduler:
    """SubagentScheduler v2: admit while summed cpus/memory_gb fit the targets, queue the rest."""

    def __init__(
        self,
        cpu_budget: float,
        mem_budget_gb: float,
        *,
        wait_timeout_s: float = DEFAULT_ADMISSION_WAIT_S,
    ) -> None:
        if cpu_budget <= 0 or mem_budget_gb <= 0:
            msg = f"cpu_budget and mem_budget_gb must be > 0, got {cpu_budget}, {mem_budget_gb}"
            raise ValueError(msg)
        if wait_timeout_s < 0:
            # Zero is allowed and means never queue: refuse anything that does not fit right
            # now. That is a policy a deployment may want, and it is how `drain` already reads
            # a bound at or below zero, so the two bounds in this class agree on their floor.
            msg = f"wait_timeout_s must be >= 0, got {wait_timeout_s}"
            raise ValueError(msg)
        self._cpu_budget = cpu_budget
        self._mem_budget_gb = mem_budget_gb
        self._wait_timeout_s = wait_timeout_s
        self._cpu_used = 0.0
        self._mem_used_gb = 0.0
        # In-flight admissions counted as an int: the drain-complete predicate must not trust
        # float residue (summed float charges can release back to a nonzero epsilon).
        self._in_flight = 0
        self._draining = False
        self._budget = asyncio.Condition()

    def _fits(self, request: PlacementRequest) -> bool:
        """Whether admitting ``request`` keeps both summed reservations within their targets."""
        return (
            self._cpu_used + request.cpus <= self._cpu_budget
            and self._mem_used_gb + request.memory_gb <= self._mem_budget_gb
        )

    @asynccontextmanager
    async def admit(self, request: PlacementRequest) -> AsyncGenerator[None, None]:
        """Reserve the request's cpus/memory_gb for the block; wait, bounded, when it is full."""
        if request.cpus > self._cpu_budget or request.memory_gb > self._mem_budget_gb:
            msg = (
                f"subagent charge (cpus={request.cpus}, memory_gb={request.memory_gb}) exceeds "
                f"the whole budget (cpus={self._cpu_budget}, memory_gb={self._mem_budget_gb}); "
                "no retry can fit it, since this is a resource-budget misconfiguration of the "
                "deployment"
            )
            raise SubagentAdmissionError(msg)
        async with self._budget:
            try:
                async with asyncio.timeout(self._wait_timeout_s):
                    while True:
                        if self._draining:
                            raise SubagentAdmissionError(POOL_DRAINING_MSG)
                        if self._fits(request):
                            break
                        await self._budget.wait()
            except TimeoutError:
                raise SubagentAdmissionError(
                    ADMISSION_WAIT_MSG.format(timeout_s=self._wait_timeout_s)
                ) from None
            self._cpu_used += request.cpus
            self._mem_used_gb += request.memory_gb
            self._in_flight += 1
        try:
            yield
        finally:
            async with self._budget:
                self._cpu_used -= request.cpus
                self._mem_used_gb -= request.memory_gb
                self._in_flight -= 1
                self._budget.notify_all()

    async def drain(self, *, timeout_s: float) -> bool:
        """Quiesce the pool for a model handoff (ADR-0030 decision 4): stop admitting, then wait."""
        async with self._budget:
            self._draining = True
            self._budget.notify_all()
            try:
                async with asyncio.timeout(timeout_s):
                    while self._in_flight > 0:
                        await self._budget.wait()
            except TimeoutError:
                return False
            return True

    def undrain(self) -> None:
        """Reverse ``drain``: resume normal admission (the conductor's ``finally``, ADR-0030)."""
        self._draining = False
