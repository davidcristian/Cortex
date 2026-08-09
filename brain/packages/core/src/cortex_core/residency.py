"""The GPU's residency: lease the resident model, and swap which model that is (ADR-0030 d5)."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from cortex_core.errors import HandoffInProgressError, ModelUnavailableError
from cortex_core.health_gate import await_model_ready
from cortex_core.model import ModelLease
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper, SubagentPlacer
from cortex_core.residency_charge import charge_handoff
from cortex_core.residency_claim import HandoffClaim
from cortex_core.residency_moves import swap_in
from cortex_core.residency_restore import restore_uninterruptibly, restore_with_retries
from cortex_core.residency_state import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_SERVING,
    ResidencyReport,
)
from cortex_core.residency_watch import BootWatch

_logger = logging.getLogger(__name__)


class SwappingModelManager:
    """ModelManager v2: one resident model at a time, swapped only inside a residency scope."""

    def __init__(
        self,
        host: ModelHost,
        endpoints: Mapping[str, str],
        plan: ResidencyPlan,
        clock: Clock,
        sleeper: Sleeper,
        placer: SubagentPlacer | None = None,
    ) -> None:
        self._host = host
        self._endpoints = dict(endpoints)
        self._plan = plan
        self._clock = clock
        self._sleeper = sleeper
        self._placer = placer
        # Which supervisor daemon every belief below was formed against (``residency_watch.py``).
        # It is asked once per handoff, because a daemon replaced under this process leaves all of
        # them describing a machine that no longer exists.
        self._boot = BootWatch(host, plan, clock=clock, sleeper=sleeper)
        # The GPU lease, with v1's discipline unchanged: one holder, waiters queue on the lock.
        self._lock = asyncio.Lock()
        # Residency bookkeeping, and the queue of acquires waiting for a scope to end. Separate
        # from the lease lock on purpose: an acquire must never hold this while waiting for the
        # lease, or a swap (which takes the lease first) would deadlock against it.
        self._residency = asyncio.Condition()
        self._resident: str | None = plan.cortex_model
        # What ``residency()`` answers. Written by the same setter that writes ``_resident``,
        # under the same condition and with nothing awaited between them, so the seam's report
        # and the lease's own view of the GPU cannot drift apart.
        self._report: ResidencyReport = RESIDENCY_SERVING
        self._scope_model: str | None = None
        self._handoff_claim = HandoffClaim(self._residency)

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease ``model``'s endpoint for the block's duration."""
        endpoint = await self._claim(model)
        async with self._lock:
            yield ModelLease(endpoint=endpoint)

    def handoff_claim(self) -> AbstractAsyncContextManager[None]:
        """Own the whole swap sequence for this block, or refuse at once (``residency_claim``)."""
        return self._handoff_claim.held()

    async def publish_boot_residency(self, *, serving: bool) -> None:
        """Replace the constructor's seed with what boot recovery actually observed."""
        await self._boot.seed()
        async with self._residency:
            self._report = RESIDENCY_SERVING if serving else RESIDENCY_BOOT_FAILED

    def residency(self) -> ResidencyReport:
        """What the GPU is serving right now, answered synchronously and without I/O."""
        return self._report

    @asynccontextmanager
    async def swap_scope(self, model: str) -> AsyncGenerator[None, None]:
        """Make ``model`` the resident for this block, and restore the cortex on the way out."""
        await self._begin_scope(model)
        try:
            await self._swap_in(model)
            yield
        finally:
            try:
                # Uninterruptible by contract (``residency_restore.py``): a cancelled turn must
                # not be able to abandon the recovery path halfway.
                await restore_uninterruptibly(self._restore(model))
            finally:
                await self._end_scope()

    async def _claim(self, model: str) -> str:
        """The endpoint ``model`` may be leased from, once any active scope has ended."""
        endpoint = self._endpoints.get(model)
        if endpoint is None:
            msg = (
                f"model {model!r} has no configured endpoint; this deployment hosts "
                f"{sorted(self._endpoints)}"
            )
            raise ModelUnavailableError(msg)
        async with self._residency:
            while self._scope_model is not None and self._scope_model != model:
                await self._residency.wait()
            if model != self._resident:
                msg = f"model {model!r} is not resident (resident: {self._resident!r})"
                raise ModelUnavailableError(msg)
        return endpoint

    async def _begin_scope(self, model: str) -> None:
        """Claim the one residency scope, so every other model's acquire starts queuing."""
        async with self._residency:
            if self._scope_model is not None:
                msg = (
                    f"a residency scope for {self._scope_model!r} is already active, so "
                    f"{model!r} cannot be swapped in (there is one GPU)"
                )
                raise HandoffInProgressError(msg)
            self._scope_model = model

    async def _end_scope(self) -> None:
        """Release the scope and wake every acquire that queued behind it."""
        async with self._residency:
            self._scope_model = None
            self._residency.notify_all()

    async def _set_resident(self, model: str | None, report: ResidencyReport) -> None:
        """Publish which model the GPU serves (``None`` mid swap), and what to tell a human.

        The report is the one thing the resident cannot express on its own: a swap in and a swap
        back both leave nothing resident, so the direction is published rather than inferred.
        """
        async with self._residency:
            self._resident = model
            self._report = report
            self._residency.notify_all()

    async def _swap_in(self, model: str) -> None:
        """Wait out the in-flight round, then make ``model`` the resident (moves, then bookkeeping).

        The lease is taken first and held across the whole move, which is what "swaps happen
        only at lease-free boundaries" means in code: v1 never preempts a round in flight.
        """
        async with self._lock:
            # First of all, and before anything is evicted: everything below is about to be spent
            # against a daemon this process may not have spoken to since it restarted, and a
            # handoff run on beliefs formed against its predecessor is the one that is lost.
            await self._boot.reconcile(self._set_resident)
            await self._set_resident(None, RESIDENCY_LOADING)
            # Before the move, not after it: the fit check inside ``swap_in`` reads what the card
            # has free, and a spawn placed between that reading and the load would spend it.
            charge_handoff(self._placer, self._plan)
            await swap_in(self._host, self._plan, model, self._gate)
            await self._set_resident(model, RESIDENCY_DEEP)

    async def _restore(self, model: str) -> None:
        """Take the lease, then run the swap back's retry policy under it."""
        async with self._lock:
            await restore_with_retries(
                self._host, self._plan, model, self._gate, self._set_resident, self._placer
            )

    async def _gate(self, model: str) -> ModelHostState:
        """This manager's readiness gate: poll ``model`` until it settles or the bound elapses."""
        return await await_model_ready(
            self._host, model, clock=self._clock, sleeper=self._sleeper, plan=self._plan
        )
