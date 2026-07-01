"""ResourceBudgetScheduler: a pure soft CPU/RAM admission budget (asyncio, no I/O, see ADR-0012)."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.placement import PlacementRequest


class ResourceBudgetScheduler:
    """SubagentScheduler v2: admit while summed cpus/memory_gb fit the targets, queue the rest."""

    def __init__(self, cpu_budget: float, mem_budget_gb: float) -> None:
        if cpu_budget <= 0 or mem_budget_gb <= 0:
            msg = f"cpu_budget and mem_budget_gb must be > 0, got {cpu_budget}, {mem_budget_gb}"
            raise ValueError(msg)
        self._cpu_budget = cpu_budget
        self._mem_budget_gb = mem_budget_gb
        self._cpu_used = 0.0
        self._mem_used_gb = 0.0
        self._budget = asyncio.Condition()

    def _fits(self, request: PlacementRequest) -> bool:
        """Whether admitting ``request`` keeps both summed reservations within their targets."""
        return (
            self._cpu_used + request.cpus <= self._cpu_budget
            and self._mem_used_gb + request.memory_gb <= self._mem_budget_gb
        )

    @asynccontextmanager
    async def admit(self, request: PlacementRequest) -> AsyncGenerator[None, None]:
        """Reserve the request's cpus/memory_gb for the block; wait when the budget is full."""
        if request.cpus > self._cpu_budget or request.memory_gb > self._mem_budget_gb:
            msg = (
                f"subagent charge (cpus={request.cpus}, memory_gb={request.memory_gb}) exceeds the "
                f"whole budget (cpus={self._cpu_budget}, memory_gb={self._mem_budget_gb})"
            )
            raise ValueError(msg)
        async with self._budget:
            while not self._fits(request):
                await self._budget.wait()
            self._cpu_used += request.cpus
            self._mem_used_gb += request.memory_gb
        try:
            yield
        finally:
            async with self._budget:
                self._cpu_used -= request.cpus
                self._mem_used_gb -= request.memory_gb
                self._budget.notify_all()
