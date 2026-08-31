"""ResourceBudgetScheduler: a pure soft CPU/RAM admission budget (asyncio, no I/O, see ADR-0012).

It owns policy rather than a machine: a two-dimensional soft budget caps the summed
``cpus``/``memory_gb`` of admitted subagents. Under GPU-first placement (ADR-0012) this is the
CPU-side counterpart to the ``SubagentPlacer``'s VRAM ledger and ``ModelManager``'s exclusive GPU
lease. They are three separate resources, composed at the runner (ADR-0010 decision 6). ``admit``
blocks until the request fits the remaining budget and releases it on exit; over budget, callers
queue (depth-1 delegation means no spawn waits on another spawn (ADR-0010), so this cannot
deadlock) for at most ``wait_timeout_s`` seconds, past which the queue is refused rather than
joined forever. A charge larger than the whole budget can never be admitted, so it raises
``SubagentAdmissionError`` rather than waiting at all: the budget's permanent wall. It is soft in
the sense that it binds nothing it did not admit (no ``.wslconfig``/parent cgroup, the user's
constraint), while what it does charge is a hard cap, because a waiting spawn holds none of the
budget. The scheduler also owns the swap-time quiesce
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

# What a refused admit says when the wait bound elapsed with the budget still full (the ADR-0012
# bounded-admission-wait addendum). The third refusal, and the only one that costs the caller
# time before it arrives: the permanent wall says no budget could ever hold this charge, the
# drain window says come back when the handoff ends, and this one says the work queued ahead
# outlasted what the deployment will wait. Phrased so the cortex does not simply spawn it again,
# which would join the back of the queue that just refused it.
ADMISSION_WAIT_MSG = (
    "waited {timeout_s:g}s for room in the subagent budget and it never came; the work queued "
    "ahead of this spawn outlasts the deployment's admission bound, so spawning it again now "
    "would join the back of the same queue"
)

# How long an admit may queue before it is refused rather than waiting forever. Derived rather than
# chosen by feel, and it has to clear two different things at once (the addendum above carries the
# arithmetic).
#
# The first is the worst wait a batch that is working can legitimately produce. One full
# MAX_SPAWN_BATCH of 8 against the shipped budget admits two at once, and how fast those two free
# their slots depends on where they land. One roster entry holds a backend, and so a model lease,
# per placement target, so its pair overlaps whenever one spawn is GPU-placed and the other
# overflows, and serializes only when both land on the same target, which is what a closed GPU tier
# leaves. Measured on a full batch of eight rather than reasoned from single subtasks, the eighth
# spawn is admitted 1624.6 s in while the entry serializes and 893.2 s in while its pair overlaps,
# so twice the serial figure is about 3250 s. Anything under that would refuse work that was going
# to run, which is worse than the unbounded wait it replaces: it turns a slow success into a
# failure.
#
# The second is the longest one task can hold the room that queue is waiting for, which is
# ATTEMPTS_PER_ADMISSION whole run deadlines, since a GPU-placed inference failure is re-run once
# on the CPU inside the same admission under a deadline armed fresh. At the shipped deadline that
# is 4800 s, above the first figure, so the hold is what binds here and the bound is stated in
# deadlines: three of them, the two a task can spend plus one of margin, which is also about four
# times the serial batch wait and covers two full batches queued at once on either placement. A
# peer therefore never stops waiting on a run that is still inside the time this deployment granted
# it, which is the relation `SubagentsConfig` enforces at boot rather than merely stating.
#
# Four places outside this module state the number rather than derive it: the delegation runbook's
# env paragraph, the two module contracts, and the sibling module's ordering above the deadline it
# declares. `scripts/crosscheck.py` holds all four to this declaration. The arithmetic those
# same paragraphs carry is deliberately not held: it is a consequence of this bound and of a
# measurement, not a second spelling of either.
DEFAULT_ADMISSION_WAIT_S = 7200.0


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
        # In-flight admissions counted as an int: the drain-complete predicate must not depend on
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
        """Reserve the request's cpus/memory_gb for the block; wait, bounded, when it is full.

        Three refusals, each the typed ``SubagentAdmissionError`` carrying its own guidance. A
        charge exceeding the whole budget could never be admitted, so it fails fast instead of
        waiting forever: the permanent wall (ADR-0012 admission-wall addendum). A drained pool
        refuses too, but transiently (ADR-0030): while a model handoff quiesces the pool, every
        admit is refused rather than queued, including a caller already waiting on a full budget
        when the drain begins (``drain`` wakes it so it refuses instead of sleeping through the
        swap). And a wait that outlasts ``wait_timeout_s`` refuses rather than queuing forever
        (the bounded-admission-wait addendum), which is the one refusal the caller waits out
        before receiving it, so the bound is sized above both the worst wait the shipped batch cap
        was measured producing and the longest one admitted task can hold the room being waited
        for, which is more than one run deadline wherever a placed attempt may be re-run.

        Anything else queues: a transient full budget admits seconds later as peers release, and
        depth-1 guarantees the queue itself drains. ``notify_all`` on release wakes every waiter
        because their asks differ. A freed slot may satisfy a small waiter but not a large one,
        so each must re-check ``_fits``. The bound is ``asyncio.timeout``, deliberately the same
        mechanism ``drain`` uses on this very condition: a duration belongs on the loop's
        monotonic clock rather than on the wall clock the ``Clock`` port reads, and an
        already-expired bound is how both of this class's waits are exercised without a test
        ever sleeping.
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
