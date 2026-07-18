"""The GPU's residency: lease the resident model, and swap which model that is (ADR-0030 d5).

``SwappingModelManager`` is Model Manager v2, still pure policy with no I/O of its own: it
implements the **unchanged** ``ModelManager`` port (``acquire`` leases the resident model's
endpoint under one lock, exactly as v1 did) and additionally the segregated
``ResidencyController`` port, whose ``swap_scope`` is the only thing in the system that changes
which model is resident. Process lifecycle happens through the injected ``ModelHost``; this
module owns *when*, never *how*.

Why a scope rather than a swapping ``acquire``: the brain's tool loop re-acquires once per
round, so an ``acquire`` that swapped would thrash (any interleaved cortex acquire would swap
back mid-task, minutes each way). The scope is the second coordination primitive instead: swaps
happen only at lease-free boundaries, exactly once per handoff, and while one is active every
other model's ``acquire`` waits for restoration rather than failing (ADR-0030 decision 5).

Fail-safe direction, the module's whole shape: the standing residency is restored in the scope's
``finally``, so it runs on success, on a failed swap-in, on an exception from the scope's body,
and on cancellation alike. It is the recovery path, not an optimization. Standing residency is
the cortex plus every tier the swap evicted for the deep model's sake, so the exit puts all of
it back rather than the cortex alone.

The one-handoff rule is here too, and it is a *claim*, not a check: ``handoff_claim`` is taken
before the conductor drains anything and refuses a concurrent handoff on the spot, because a
precondition read from a store and acted on later is a race that lets two handoffs into the
prologue and lets the loser reopen the drain window under the winner.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager

from cortex_core.errors import (
    HandoffInProgressError,
    ModelUnavailableError,
    ResidencyRestoreError,
)
from cortex_core.health_gate import await_model_ready
from cortex_core.model import ModelLease
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper
from cortex_core.residency_moves import restore_standing, swap_in

# How many times the scope's exit tries to bring the cortex back before it gives up loudly: the
# first attempt plus the one retry ADR-0030 decision 4 step 3 specifies. A third would not be a
# different experiment; past two, the host itself is gone and only the runbook helps.
_RESTORE_ATTEMPTS = 2

_logger = logging.getLogger(__name__)


class SwappingModelManager:
    """ModelManager v2: one resident model at a time, swapped only inside a residency scope.

    ``endpoints`` maps each logical model id to the base URL that serves it, composition-root
    config (never discovered here, since this stays pure); ``plan`` says which of them is the
    standing resident, which one a handoff swaps in, and what the swap's bounds are.
    """

    def __init__(
        self,
        host: ModelHost,
        endpoints: Mapping[str, str],
        plan: ResidencyPlan,
        clock: Clock,
        sleeper: Sleeper,
    ) -> None:
        self._host = host
        self._endpoints = dict(endpoints)
        self._plan = plan
        self._clock = clock
        self._sleeper = sleeper
        # The GPU lease, with v1's discipline unchanged: one holder, waiters queue on the lock.
        self._lock = asyncio.Lock()
        # Residency bookkeeping, and the queue of acquires waiting for a scope to end. Separate
        # from the lease lock on purpose: an acquire must never hold this while waiting for the
        # lease, or a swap (which takes the lease first) would deadlock against it.
        self._residency = asyncio.Condition()
        self._resident: str | None = plan.cortex_model
        self._scope_model: str | None = None
        # Whether a handoff already owns the whole swap sequence, claimed before anything is
        # drained. Separate from the scope: a claim is held through the drain, while the cortex
        # is still serving and must still be leasable, so it must not queue other acquires.
        self._handoff_claimed = False

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        """Queue for the GPU, then lease ``model``'s endpoint for the block's duration.

        Unchanged from v1 in signature and in its one-lock-per-GPU semantics. Two things the
        swap adds: while a residency scope is active, an acquire of any other model **waits**
        for the scope to end rather than raising, so a queued cortex turn on another stream
        blocks through the handoff and then runs; and a model with no configured endpoint, or
        one that is not resident outside any scope, still raises ``ModelUnavailableError``.

        An acquire that passes the residency check just as a scope begins still gets its whole
        round: the swap waits for the lease to fall free, so v1's "never preempt a mid-stream
        round" holds, and at most one further round can slip in before the swap.
        """
        endpoint = await self._claim(model)
        async with self._lock:
            yield ModelLease(endpoint=endpoint)

    @asynccontextmanager
    async def handoff_claim(self) -> AsyncGenerator[None, None]:
        """Own the whole swap sequence for this block, or refuse at once because someone does.

        The one-GPU-one-handoff rule, taken **before** the conductor drains or evicts anything
        rather than checked in a store and acted on two awaits later. Check and claim happen
        under this object's own condition with nothing awaited between them, so two escalating
        turns racing on separate streams cannot both pass: the loser is refused while the
        machine is untouched, which is what lets it be told the honest thing (a handoff is
        running) instead of the swap-failure note.

        Releasing is a bare assignment on the way out, deliberately taking no lock: the release
        is owed even to a cancelled caller, and nothing waits on this claim to be woken.
        """
        async with self._residency:
            if self._handoff_claimed:
                msg = (
                    "a brain handoff is already in flight, so this one was not started (there "
                    "is one GPU)"
                )
                raise HandoffInProgressError(msg)
            self._handoff_claimed = True
        try:
            yield
        finally:
            self._handoff_claimed = False

    @asynccontextmanager
    async def swap_scope(self, model: str) -> AsyncGenerator[None, None]:
        """Make ``model`` the resident for this block, and restore the cortex on the way out.

        Entering: claim the scope (a second concurrent scope is refused, there being one GPU),
        wait for the lease to fall free, evict the cortex and any other hosted tier, start
        ``model``, and health-gate it. Leaving, in a ``finally`` that covers success, failure,
        and cancellation: stop ``model``, start the cortex, health-gate it, retrying once.
        """
        await self._begin_scope(model)
        try:
            await self._swap_in(model)
            yield
        finally:
            try:
                await self._restore_uninterruptibly(model)
            finally:
                await self._end_scope()

    async def _restore_uninterruptibly(self, model: str) -> None:
        """Run the restore to completion even while this caller is being cancelled.

        The swap back is the recovery path, so it is the one thing a cancelled turn must not be
        able to abandon: a client that disconnects mid handoff would otherwise leave the deep
        model resident and the GPU serving nothing this process can lease again. It therefore
        runs as its own task behind a shield, and every cancellation waits for that task before
        it propagates, which keeps the ordering the scope promises (restored, then released).

        **Every** cancellation, not the first one, and that is the whole point of the loop: one
        shielded wait is abandoned by a second delivery, and the seam delivers two whenever a
        client ``Cancel`` is followed by the stream's own teardown (``ConverseStream`` cancels
        the turn from the pump, then again from ``events()``'s ``finally``). A restore left
        running behind the scope's exit is the harm: the conductor reopens subagent admission
        the moment the scope returns, so admission would reopen onto a cortex still stopped and
        a tier not yet restarted. The wait is bounded by the restore itself, not by the number
        of cancellations, since every iteration makes the same progress the first one did.
        """
        restore = asyncio.create_task(self._restore(model))
        cancelled: asyncio.CancelledError | None = None
        while not restore.done():
            try:
                await asyncio.shield(restore)
            except asyncio.CancelledError as err:
                cancelled = err
            except ResidencyRestoreError:
                # Raised below instead, so that a cancellation delivered first still wins: the
                # caller is being torn down and that is the graver thing to tell it about.
                pass
        if cancelled is not None:
            # Retrieved so asyncio does not warn about it; a restore failure has already been
            # logged loudly inside, and the cancellation is what the caller must see.
            restore.exception()
            raise cancelled
        await restore

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
        """Claim the one residency scope, so every other model's acquire starts queuing.

        The backstop under ``handoff_claim``: a caller that swaps without claiming first is
        still refused, and with the same typed error, because a second swap is a second handoff
        however it was reached and never a swap that broke.
        """
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

    async def _set_resident(self, model: str | None) -> None:
        """Publish which model the GPU now serves (``None`` while a swap is in flight)."""
        async with self._residency:
            self._resident = model
            self._residency.notify_all()

    async def _swap_in(self, model: str) -> None:
        """Wait out the in-flight round, then make ``model`` the resident (moves, then bookkeeping).

        The lease is taken first and held across the whole move, which is what "swaps happen
        only at lease-free boundaries" means in code: v1 never preempts a round in flight.
        """
        async with self._lock:
            await self._set_resident(None)
            await swap_in(self._host, self._plan, model, self._gate)
            await self._set_resident(model)

    async def _restore(self, model: str) -> None:
        """Bring the cortex back, retrying once; give up loudly rather than silently.

        Runs with the lease held, so nothing can lease a half-restored GPU, and it waits out any
        round the scope's own resident still had in flight.
        """
        cortex = self._plan.cortex_model
        async with self._lock:
            await self._set_resident(None)
            for attempt in range(1, _RESTORE_ATTEMPTS + 1):
                if await restore_standing(self._host, self._plan, model, self._gate):
                    await self._set_resident(cortex)
                    return
                _logger.warning(
                    "restoring the cortex failed; retrying",
                    extra={"model": cortex, "attempt": attempt},
                )
            _logger.error(
                "could not restore the cortex after a model swap; the GPU serves nothing",
                extra={"model": cortex, "attempts": _RESTORE_ATTEMPTS},
            )
            msg = (
                f"could not restore {cortex!r} after {_RESTORE_ATTEMPTS} attempts; manual "
                "recovery is needed (docs/runbooks/model-swap.md)"
            )
            raise ResidencyRestoreError(msg)

    async def _gate(self, model: str) -> ModelHostState:
        """This manager's readiness gate: poll ``model`` until it settles or the bound elapses."""
        return await await_model_ready(
            self._host, model, clock=self._clock, sleeper=self._sleeper, plan=self._plan
        )
