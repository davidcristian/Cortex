"""ResourceBudgetScheduler: a pure soft CPU/RAM admission budget (asyncio, no I/O, see ADR-0012).

Owns policy, not a machine: a two-dimensional soft budget caps the summed ``cpus``/``memory_gb`` of
admitted subagents. Under GPU-first placement (ADR-0012) this is the CPU-side counterpart to the
``SubagentPlacer``'s VRAM ledger and ``ModelManager``'s exclusive GPU lease. They are three separate
resources, composed at the runner (ADR-0010 decision 6). ``admit`` blocks until the request fits
the remaining budget and releases it on exit; over budget, callers queue (depth-1 delegation means
no spawn waits on another spawn (ADR-0010), so this cannot deadlock). A charge larger than the whole
budget can never be admitted, so it raises ``SubagentAdmissionError`` rather than waiting forever:
the budget's permanent wall. It is soft in the sense that it binds nothing it did not admit (no
``.wslconfig``/parent cgroup, the user's constraint), yet what it *does* charge is a hard cap,
because a waiting spawn holds none of the budget. The scheduler also owns the swap-time quiesce
(ADR-0030 decision 4, the ADR-0012 deferral): ``drain`` stops admission for a model handoff and
waits, bounded, for in-flight admissions to release; ``undrain`` reverses it. Doing no I/O, it is
a pure reference impl of the ``SubagentScheduler`` port, in the core, fully covered with no real
workload.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.errors import SubagentAdmissionError
from cortex_core.placement import PlacementRequest

# What a refused admit says while the pool is draining for a brain handoff (ADR-0030 decision 4).
# Refuse, not queue: a brain-phase spawn queued against its own drain would deadlock the turn
# against its own swap. The runner degrades this to an ok=False result the model reads, so the
# text says the window is transient rather than a deployment defect.
POOL_DRAINING_MSG = "pool draining for a model handoff; delegation resumes when the handoff ends"


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
        """Reserve the request's cpus/memory_gb for the block; wait when the budget is full.

        Two refusals, both the typed ``SubagentAdmissionError`` carrying their own guidance. A
        charge exceeding the whole budget could never be admitted, so it fails fast instead of
        waiting forever: the permanent wall (ADR-0012 admission-wall addendum). A drained pool
        refuses too, but transiently (ADR-0030): while a model handoff quiesces the pool, every
        admit is refused rather than queued, including a caller already waiting on a full budget
        when the drain begins (``drain`` wakes it so it refuses instead of sleeping through the
        swap). Anything else queues: a transient full budget admits seconds later as peers
        release, and depth-1 guarantees the queue itself drains. ``notify_all`` on release wakes
        every waiter because their asks differ. A freed slot may satisfy a small waiter but not a
        large one, so each must re-check ``_fits``.
        """
        if request.cpus > self._cpu_budget or request.memory_gb > self._mem_budget_gb:
            msg = (
                f"subagent charge (cpus={request.cpus}, memory_gb={request.memory_gb}) exceeds "
                f"the whole budget (cpus={self._cpu_budget}, memory_gb={self._mem_budget_gb}); "
                "no retry can fit it, since this is a resource-budget misconfiguration of the "
                "deployment"
            )
            raise SubagentAdmissionError(msg)
        async with self._budget:
            while True:
                if self._draining:
                    raise SubagentAdmissionError(POOL_DRAINING_MSG)
                if self._fits(request):
                    break
                await self._budget.wait()
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
        """Quiesce the pool for a model handoff (ADR-0030 decision 4): stop admitting, then wait.

        Entering the drain window is immediate: from this call on (and until ``undrain``), every
        ``admit`` refuses with ``POOL_DRAINING_MSG``, and callers already queued on the budget are
        woken so they refuse now rather than deadlock the handoff turn against its own swap. The
        wait for in-flight admissions to release is bounded by ``timeout_s`` seconds (the
        conductor passes ``CORTEX_SWAP_DRAIN_TIMEOUT_S``; a bound at or below zero is already
        expired, checking without waiting). True means the pool drained clean. False means the
        bound elapsed with work still in flight; nothing is killed (v1 never kills a subagent
        mid-stream), the caller must abort the swap before evicting anything, and the window
        stays in force either way until ``undrain``. Idempotent: a concurrent second drain waits
        alongside the first and resolves on the same release signal.
        """
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
        """Reverse ``drain``: resume normal admission (the conductor's ``finally``, ADR-0030).

        Called on swap-back and on an aborted handoff alike, so admission always resumes.
        Synchronous and idempotent; a bare flag flip is race-free here because no admit can be
        asleep during the window (drain woke and refused every waiter, and a draining admit
        refuses before it ever waits), so there is nobody to notify.
        """
        self._draining = False
