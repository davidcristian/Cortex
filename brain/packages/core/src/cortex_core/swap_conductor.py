"""The swap sequence: serialize, drain, swap, run, persist, swap back (ADR-0030 decision 4).

This is the one hard rule as executable code. The conductor runs after the cortex phase's
generator has finished, at a loop boundary where no lease is held and everything the cortex
produced is already in a store, and it composes the pieces that each own one guarantee:
``HandoffStore`` (the record survives), ``SubagentScheduler.drain`` (nothing else is running
when the GPU changes hands), ``ResidencyController.swap_scope`` (the swap happens at a
lease-free boundary and the cortex comes back in a ``finally``), and ``BrainPhase`` (the deep
model rehydrates from the store rather than from anything in memory).

Fail-safe direction throughout: **every exit path converges back to a serving cortex**, and
every one of them leaves the record in a terminal state and tells the user what happened. The
ordering is load-bearing and each step's failure has a direction:

0. **Claim.** Take the one-handoff claim on the residency controller, before anything at all,
   because the check and the act must not be two awaits apart: a second escalating turn that
   slipped through would drain the pool, be refused at the swap, and then reopen admission in
   its own ``finally`` while the winner's deep model was still resident. Losing it costs
   nothing, and the user is told the truthful thing, that a handoff is already running.
1. **Snapshot.** Refuse a turn that read the screen (here and not in the escalation tool,
   because the capture may happen AFTER the handoff was approved), then a deployment whose model
   host has no deep tier to load at all, then one the store still thinks is live, then persist
   the record ``READY``. Nothing has been stopped, so a failure here costs nothing but the
   handoff. The middle refusal is the one that has to be here rather than later: the tier's
   absence would otherwise surface at the ``start`` in step 3, with the cortex already unloaded
   and the scope's ``finally`` owing minutes to put it back, for a handoff that could never run.
2. **Drain.** Quiesce the subagent pool, bounded. A timeout **aborts before anything is
   evicted**: v1 never kills a subagent mid-stream, so a straggler stops the swap rather than
   half-swapping the machine. ``undrain`` is owed in a ``finally``, swap-back and abort alike,
   and owed **after** the swap generator is closed, since closing it restores the standing
   residency: a window reopened onto a still-stopped tier would place delegated work on a
   server nothing has restarted. A ``coresident`` plan stops no such tier, so it skips the
   whole step and delegation keeps flowing, the deep phase's own spawns included.
3. **Swap in and run.** Inside the residency scope, mark the record ``BRAIN_ACTIVE`` only once
   the deep model is actually serving, then stream its phase onto this turn's own stream.
4. **Swap back.** The scope's ``finally``. A clean handoff then marks the record ``DONE`` and
   deletes it; every failure marks it ``FAILED`` and keeps it under the store's diagnosis TTL.
   A settling write the store refuses drops the record instead of keeping it, because that
   delete is also what releases the store's claim (``swap_settle.py`` has the whole argument).

Boot recovery, the other half of the rule, lives in ``swap_recovery.py``.
"""

import logging
from collections.abc import AsyncGenerator

from cortex_core.brain_phase import BrainPhase
from cortex_core.errors import (
    HandoffInProgressError,
    HandoffStoreError,
    InferenceError,
    ModelManagerError,
)
from cortex_core.events import StatusUpdate, TextDelta, TurnEvent
from cortex_core.handoff import EscalationSlot, HandoffRecord, HandoffState
from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import Clock, HandoffStore, ResidencyController, SubagentScheduler
from cortex_core.swap_notes import (
    ALREADY_ACTIVE_NOTE,
    DRAIN_TIMEOUT_NOTE,
    DRAINING_DETAIL,
    LOADING_DETAIL,
    OPAQUE_TURN_NOTE,
    RESTORING_DETAIL,
    STORE_FAILED_NOTE,
    SWAPPING_STATE,
    UNHOSTED_TIER_NOTE,
    WORKING_DETAIL,
    note_for,
)
from cortex_core.swap_settle import HandoffSettler

_logger = logging.getLogger(__name__)


def _status(detail: str) -> StatusUpdate:
    """One swap-window progress event, under the state the overlay renders as a chip."""
    return StatusUpdate(state=SWAPPING_STATE, detail=detail)


class SwapConductor:
    """Runs one brain handoff end to end, as a stream of events for the escalating turn.

    ``scheduler`` is ``None`` with no subagent pool, and a ``coresident`` plan takes down no
    tier the pool feeds, so both leave the drain unowed for one reason: nothing to protect.
    Everything else is required, every collaborator a port, so the sequence runs over fakes.
    """

    def __init__(
        self,
        handoffs: HandoffStore,
        residency: ResidencyController,
        brain_phase: BrainPhase,
        plan: ResidencyPlan,
        clock: Clock,
        scheduler: SubagentScheduler | None = None,
    ) -> None:
        self._handoffs = handoffs
        self._residency = residency
        self._brain_phase = brain_phase
        self._plan = plan
        self._clock = clock
        self._scheduler = scheduler
        self._settle = HandoffSettler(handoffs)

    async def run_handoff(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run the whole sequence for one filled slot, streaming status, text, and notes.

        Called at the loop boundary by the escalating turn wrapper, with the cortex phase's
        generator already closed, so no GPU lease is held and nothing is copied mid-flight.
        Yields nothing but events: whether the handoff happened is told on the stream, never
        raised at the caller, except when the turn itself is being torn down.

        The claim wraps everything, so a handoff that loses it has drained nothing and evicted
        nothing, and the whole sequence below runs only for the one turn that owns the GPU.
        """
        try:
            async with self._residency.handoff_claim():
                run = self._run_claimed(slot, session_id=session_id, turn_id=turn_id)
                try:
                    async for event in run:
                        yield event
                finally:
                    # Same deterministic teardown as every other generator here: a consumer
                    # that walks away must unwind the sequence, not leave it to the collector.
                    await run.aclose()
        except HandoffInProgressError:
            _logger.warning(
                "refusing a handoff while another one holds the swap", extra={"turn": turn_id}
            )
            yield TextDelta(text=ALREADY_ACTIVE_NOTE)

    async def _run_claimed(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """The sequence itself, run by the one turn that holds the claim."""
        prepared = await self._prepare(slot, session_id=session_id, turn_id=turn_id)
        if isinstance(prepared, str):
            yield TextDelta(text=prepared)
            return
        try:
            if not self._plan.coresident:
                yield _status(DRAINING_DETAIL)
            if not await self._drain():
                # The abort direction: nothing has been evicted, so the cortex is still serving
                # and the turn simply ends with what it has.
                await self._settle.advance(prepared, HandoffState.FAILED)
                yield TextDelta(text=DRAIN_TIMEOUT_NOTE)
                return
            swap = self._swap(prepared)
            try:
                async for event in swap:
                    yield event
            finally:
                # Deterministic teardown of the inner generator: a consumer that closes this
                # one must unwind the residency scope, not abandon it to the garbage collector.
                # This is also what keeps the drain window shut across the swap back, since it
                # is nested INSIDE the undrain's ``finally``: closing the swap restores the
                # standing residency, and only then may admission reopen. Hoisting the undrain
                # above this line would hand delegated work to a tier still stopped.
                await swap.aclose()
        except BaseException:
            # Cancellation and stream teardown included: a handoff that stops being run is a
            # failed handoff, and a live record would otherwise strand the next boot. The write
            # is best-effort under cancellation, which is exactly what boot recovery backs up.
            await self._settle.advance(prepared, HandoffState.FAILED)
            raise
        finally:
            # Admission reopens here and nowhere else, so this is the line the drain window's
            # whole lifetime hangs off: it runs on every path (a drain that timed out, a swap
            # that failed, a clean handoff, a teardown) and it runs LAST, after the swap
            # generator above has been closed and has therefore restored the standing residency.
            self._undrain()

    async def _prepare(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> HandoffRecord | str:
        """Serialize the slot into a ``READY`` record, or the note saying why there is none."""
        if slot.refs is not None and slot.refs.taint.opaque:
            # Pixels are turn-local (ADR-0029 decision 6): no store persists them, so the deep
            # model would get a tool message promising a picture with none attached. Keyed on
            # the ``opaque`` bit, the fact that stays true where the pixels cannot travel.
            _logger.warning(
                "refusing a handoff for a turn that read the screen", extra={"turn": turn_id}
            )
            return OPAQUE_TURN_NOTE
        if await self._residency.unhosted(self._plan.brain_model):
            # Before the store is touched and long before the drain, which is the whole worth of
            # the check: this deployment's host has no such tier, so the start in step 3 would
            # refuse after the cortex was already unloaded. Asked every time rather than
            # remembered, because the daemon that answers is replaceable by one whose roster was
            # fixed, and a brain that cached the verdict would refuse a deployment that now works.
            _logger.error(
                "escalation was asked for but the model host does not serve the deep model, so "
                "the handoff was refused with nothing drained and nothing unloaded: name an "
                "artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or turn escalation off "
                "(CORTEX_ESCALATION)",
                extra={"model": self._plan.brain_model, "turn": turn_id},
            )
            return UNHOSTED_TIER_NOTE
        try:
            if (active := await self._handoffs.active()) is not None:
                # The claim already refused anything racing this turn in this process, so a
                # record still live here is one the store kept: a settle that never landed, or
                # a handoff another process owns. Either way this turn evicts nothing.
                _logger.warning(
                    "refusing a handoff while the store still has one in flight",
                    extra={"active_handoff": active.handoff_id, "turn": turn_id},
                )
                return ALREADY_ACTIVE_NOTE
            record = slot.snapshot(
                turn_id=turn_id, session_id=session_id, requested_at=self._clock.now()
            )
        except HandoffStoreError:
            _logger.exception("the handoff store failed before anything was evicted")
            return STORE_FAILED_NOTE
        return await self._persist_snapshot(record)

    async def _persist_snapshot(self, record: HandoffRecord) -> HandoffRecord | str:
        """Write the ``READY`` record, and never leave it live if the write is interrupted.

        A handoff killed at this exact boundary would otherwise strand a non-terminal record
        that ``active()`` keeps answering with, and every later escalation would be refused as
        a second concurrent handoff until the next restart. So the teardown paths fail it here
        too, where the record object still exists to be failed.
        """
        try:
            await self._handoffs.put(record)
        except HandoffStoreError:
            _logger.exception("the handoff store failed before anything was evicted")
            return STORE_FAILED_NOTE
        except BaseException:
            await self._settle.advance(record, HandoffState.FAILED)
            raise
        return record

    async def _swap(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Swap in, run the deep model's phase, swap back, and settle the record."""
        try:
            yield _status(LOADING_DETAIL)
            async with self._residency.swap_scope(self._plan.brain_model):
                # Only now is the deep model actually serving: the record reaches BRAIN_ACTIVE
                # after the health gate passed, never on the strength of a start call.
                await self._settle.advance(record, HandoffState.BRAIN_ACTIVE)
                yield _status(WORKING_DETAIL)
                phase = self._brain_phase.run(record)
                try:
                    async for event in phase:
                        yield event
                finally:
                    await phase.aclose()
                yield _status(RESTORING_DETAIL)
        except InferenceError:
            # The deep model died mid-work. Its phase has already streamed and persisted its
            # partial answer with the honest note, so there is nothing to add here: the scope's
            # finally has restored the cortex and the record is what is left to settle.
            await self._settle.advance(record, HandoffState.FAILED)
            return
        except ModelManagerError as err:
            await self._settle.advance(record, HandoffState.FAILED)
            yield TextDelta(text=note_for(err))
            return
        await self._settle.advance(record, HandoffState.DONE)

    async def _drain(self) -> bool:
        """Quiesce the pool, or answer True when there is no pool, or none to quiesce it for."""
        if self._scheduler is None or self._plan.coresident:
            return True
        return await self._scheduler.drain(timeout_s=self._plan.drain_timeout_s)

    def _undrain(self) -> None:
        """Resume admission, whatever ended the handoff (the drain window is never leaked)."""
        if self._scheduler is not None:
            self._scheduler.undrain()
