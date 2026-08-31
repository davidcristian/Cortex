"""The GPU's residency: lease the resident model, and swap which model that is."""

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from cortex_core.errors import ModelUnavailableError
from cortex_core.health_gate import await_model_ready
from cortex_core.model import ModelLease
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper, SubagentPlacer
from cortex_core.residency_board import ResidencyBoard
from cortex_core.residency_charge import charge_handoff
from cortex_core.residency_claim import HandoffClaim
from cortex_core.residency_moves import is_unhosted, swap_in
from cortex_core.residency_pace import HandoffPace
from cortex_core.residency_probe import ResidencyProbeMixin
from cortex_core.residency_regain import heal_standing_residency
from cortex_core.residency_restore import restore_uninterruptibly, restore_with_retries
from cortex_core.residency_state import RESIDENCY_DEEP, RESIDENCY_LOADING
from cortex_core.residency_tiers import StandingTiers
from cortex_core.residency_watch import BootWatch


class SwappingModelManager(ResidencyProbeMixin):
    """One resident model at a time, swapped only inside a residency scope."""

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
        self._tiers = StandingTiers(placer)
        self._pace = HandoffPace(clock)
        self._boot = BootWatch(host, plan, self._tiers, clock=clock, sleeper=sleeper)
        # Two locks, not one: an acquire must never hold the lease while it waits for a scope
        # to end, because a swap takes the lease first and the two would deadlock.
        self._lock = asyncio.Lock()
        self._board = ResidencyBoard(plan.cortex_model)
        self._handoff_claim = HandoffClaim(self._board.condition)

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease ``model``'s endpoint for the block's duration."""
        endpoint = await self._claim(model)
        async with self._lock:
            yield ModelLease(endpoint=endpoint)

    async def unhosted(self, model: str) -> bool:
        """Whether the daemon answering right now has no such logical model at all."""
        return await is_unhosted(self._host, model)

    def handoff_claim(self) -> AbstractAsyncContextManager[None]:
        """Own the whole swap sequence for this block, or raise at once."""
        return self._handoff_claim.held()

    @asynccontextmanager
    async def swap_scope(self, model: str) -> AsyncGenerator[None, None]:
        """Make ``model`` the resident for this block, and restore the cortex on the way out."""
        await self._board.enter_scope(model)
        try:
            await self._swap_in(model)
            yield
        finally:
            try:
                await restore_uninterruptibly(self._restore(model))
            finally:
                await self._board.leave_scope()

    async def _claim(self, model: str) -> str:
        """The endpoint ``model`` may be leased from, once any active scope has ended."""
        endpoint = self._endpoints.get(model)
        if endpoint is None:
            msg = (
                f"model {model!r} has no configured endpoint; this deployment hosts "
                f"{sorted(self._endpoints)}"
            )
            raise ModelUnavailableError(msg)
        await self._board.await_resident(model)
        return endpoint

    async def _swap_in(self, model: str) -> None:
        """Wait out the in-flight round, then make ``model`` the resident."""
        async with self._lock:
            # Before anything is evicted: a daemon replaced since this process last spoke to
            # it leaves every piece of residency state describing a machine that is gone.
            await self._boot.reconcile(self._board.publish)
            await self._board.publish(None, RESIDENCY_LOADING)
            # Before the load: ``swap_in`` checks the free device memory, and a subagent
            # spawned between that check and the load would take the room it found.
            charge_handoff(self._placer, self._plan)
            await swap_in(self._host, self._plan, model, self._gate)
            await self._board.publish(model, RESIDENCY_DEEP)

    async def heal_residency(self) -> None:
        """Read what the GPU is really doing and act on it, unless a handoff owns the card."""
        if self._fence():
            await heal_standing_residency(
                self._host, self._plan, self._board, self._tiers, self._fence
            )

    def _fence(self) -> bool:
        """Whether no handoff owns the GPU right now, answered synchronously and without I/O."""
        return not self._handoff_claim.claimed and not self._board.scope_active

    async def _restore(self, model: str) -> None:
        """Take the lease, then run the swap back's retry policy under it."""
        async with self._lock:
            await restore_with_retries(
                self._host, self._plan, model, self._gate, self._board.publish, self._tiers
            )

    async def _gate(self, model: str) -> ModelHostState:
        """Poll ``model`` until it settles or the plan's load bound runs out."""
        return await await_model_ready(
            self._host, model, clock=self._clock, sleeper=self._sleeper, plan=self._plan
        )
