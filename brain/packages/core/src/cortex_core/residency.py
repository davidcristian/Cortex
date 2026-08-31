"""The GPU's residency: lease the resident model, and swap which model that is (ADR-0030 d5).

``SwappingModelManager`` is pure policy with no I/O of its own. It implements the unchanged
``ModelManager`` port (``acquire`` leases the resident model's endpoint under one lock, exactly as
v1 did) plus the segregated ``ResidencyController`` port, whose ``swap_scope`` is the only thing in
the system that changes which model is resident. Process lifecycle happens through the injected
``ModelHost``; this module decides when a swap runs, never how.

ADR-0030 decision 5 argues the shape, including why this is a scope rather than a swapping
``acquire`` (the tool loop re-acquires once per round, so a swapping ``acquire`` would thrash) and
why the standing residency is restored in the scope's ``finally``, which makes that restore the
recovery path for a failed swap-in, for an exception in the scope body, and for cancellation alike.
Standing residency is the cortex plus every tier the swap evicted, so the exit puts all of it back.

The rest is delegated to the ``residency_*`` modules imported below; ``docs/modules/brain-core.md``
says what each one owns.
"""

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
    """One resident model at a time, swapped only inside a residency scope.

    ``endpoints`` maps each logical model id to the base URL that serves it, composition-root
    config (never discovered here, since this stays pure); ``plan`` says which of them is the
    standing resident, which one a handoff swaps in, and what the swap's bounds are.

    ``placer`` is optional and is only written to: at the two edges of the swap it is told which
    model holds the card, so its fit-test stops describing a cortex the handoff evicted
    (``residency_charge.py``). ``None`` is the deployment with no subagent pool.
    """

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
        # Which peers of the cortex the standing residency is missing, written wherever a start was
        # refused and read by the seam and by the retry.
        self._tiers = StandingTiers(placer)
        # How the last handoff ran. Held here rather than in the residency record because the pass
        # that republishes a serving cortex would erase anything a swap had written there.
        self._pace = HandoffPace(clock)
        # Which supervisor daemon the state below was formed against, asked once per handoff: a
        # daemon replaced under this process leaves all of it describing a machine that is gone.
        self._boot = BootWatch(host, plan, self._tiers, clock=clock, sleeper=sleeper)
        # The GPU lease: one holder, waiters queue on the lock.
        self._lock = asyncio.Lock()
        # Residency bookkeeping, and the queue of acquires waiting for a scope to end. Separate
        # from the lease lock: an acquire must never hold it while waiting for the lease, or a swap
        # (which takes the lease first) would deadlock against it.
        self._board = ResidencyBoard(plan.cortex_model)
        # Whether a handoff already owns the whole swap sequence, claimed before anything is
        # drained. Over the board's condition but on a separate flag, because a claim is held
        # through the drain, while the cortex is still serving and must stay leasable, so unlike a
        # scope it must not queue other acquires.
        self._handoff_claim = HandoffClaim(self._board.condition)

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease ``model``'s endpoint for the block's duration.

        Unchanged from v1 in signature and in its one-lock-per-GPU semantics. The swap adds one
        thing: while a residency scope is active, an acquire of any other model waits for the scope
        to end rather than raising, so a queued cortex turn on another stream blocks through the
        handoff and then runs. A model with no configured endpoint, or one that is not resident
        outside any scope, still raises ``ModelUnavailableError``.

        An acquire that passes the residency check just as a scope begins still gets its whole
        round, because the swap waits for the lease to fall free. A mid-stream round is therefore
        never preempted, and at most one further round can slip in before the swap.
        """
        endpoint = await self._claim(model)
        async with self._lock:
            yield ModelLease(endpoint=endpoint)

    async def unhosted(self, model: str) -> bool:
        """Whether the daemon answering right now carries no such logical model at all.

        Asked by the conductor before anything is drained or evicted, and answered by asking the
        host rather than from cached state (``residency_moves.is_unhosted``): a single ``status``
        call is cheap enough to re-derive at the moment it is used, unlike the rest of the state
        here, which is expensive and so is rebuilt on an event instead.
        """
        return await is_unhosted(self._host, model)

    def handoff_claim(self) -> AbstractAsyncContextManager[None]:
        """Own the whole swap sequence for this block, or raise at once (``residency_claim``).

        Taken before the conductor drains or evicts anything, and held for the whole sequence. It
        does not queue other acquires the way a scope does, because the cortex is still resident
        and still leasable throughout the drain it covers.
        """
        return self._handoff_claim.held()

    @asynccontextmanager
    async def swap_scope(self, model: str) -> AsyncGenerator[None, None]:
        """Make ``model`` the resident for this block, and restore the cortex on the way out.

        Entering: claim the scope (a second concurrent scope is refused, there being one GPU),
        wait for the lease to fall free, evict the cortex and any other hosted tier, start
        ``model``, and health-gate it. Leaving, in a ``finally`` that covers success, failure,
        and cancellation: stop ``model``, start the cortex, health-gate it, retrying once.
        """
        await self._board.enter_scope(model)
        try:
            await self._swap_in(model)
            yield
        finally:
            try:
                # Uninterruptible by contract (``residency_restore.py``): a cancelled turn must not
                # be able to abandon the restore halfway.
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
        """Wait out the in-flight round, then make ``model`` the resident (moves, then bookkeeping).

        The lease is taken first and held across the whole move, which is how "swaps happen only at
        lease-free boundaries" is enforced: a round in flight is never preempted.
        """
        async with self._lock:
            # Before anything is evicted: the calls below run against a daemon this process may not
            # have spoken to since it restarted, and a handoff run on state formed against its
            # predecessor is the one that loses that state.
            await self._boot.reconcile(self._board.publish)
            await self._board.publish(None, RESIDENCY_LOADING)
            # Before the move: the fit check inside ``swap_in`` reads what the card has free, and a
            # spawn placed between that reading and the load would spend it.
            charge_handoff(self._placer, self._plan)
            await swap_in(self._host, self._plan, model, self._gate)
            await self._board.publish(model, RESIDENCY_DEEP)

    async def heal_residency(self) -> None:
        """Read what the GPU is really doing and act on it, unless a handoff owns the card.

        Driven by ``TierHealer`` (``residency_heal.py``), which owns the pacing and the task, over
        ``residency_regain.py``, which owns what a pass does: every evictable peer is asked about
        rather than only the ones already recorded as missing (ADR-0030 tier-sweep addendum), and
        then the resident itself, so a cortex that came back after a restore gave up is picked up
        here instead of being waited for by a handoff that can no longer start (ADR-0030
        residency-regain addendum).

        The lease is deliberately not taken: a peer is never the resident, so holding it across a
        control call would park a user's turn behind a status probe, and a pass that queued for it
        would be held for a whole load. ``_fence`` stands in for it, read again by the sweep before
        each start and again by the regain's publish.
        """
        if self._fence():
            await heal_standing_residency(
                self._host, self._plan, self._board, self._tiers, self._fence
            )

    def _fence(self) -> bool:
        """Whether no handoff owns the GPU right now, answered synchronously and without I/O.

        Both flags are read, because they cover different stretches of one handoff: the claim is
        taken before the conductor drains anything and held to the end, and the scope is the
        backstop under it for a swap that never claimed. This is handed down the healing pass as
        well as read here, so the sweep can ask again before a start and the regain can ask under
        the residency condition. Being a plain read of two flags, nothing can interleave between it
        and the call it guards.
        """
        return not self._handoff_claim.claimed and not self._board.scope_active

    async def _restore(self, model: str) -> None:
        """Take the lease, then run the swap back's retry policy under it."""
        async with self._lock:
            await restore_with_retries(
                self._host, self._plan, model, self._gate, self._board.publish, self._tiers
            )

    async def _gate(self, model: str) -> ModelHostState:
        """This manager's readiness gate: poll ``model`` until it settles or the bound elapses."""
        return await await_model_ready(
            self._host, model, clock=self._clock, sleeper=self._sleeper, plan=self._plan
        )
