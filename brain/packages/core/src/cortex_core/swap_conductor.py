"""The swap sequence: serialize, drain, swap, run, persist, swap back (ADR-0030 decision 4).

The conductor runs after the cortex phase's generator has finished, at a loop boundary where no
lease is held and everything the cortex produced is already in a store. It composes the pieces
that each own one guarantee: ``HandoffStore`` (the record survives), ``SubagentScheduler.drain``
(nothing else is running when the GPU changes hands), ``ResidencyController.swap_scope`` (the swap
happens at a lease-free boundary and the cortex comes back in a ``finally``), and ``BrainPhase``
(the deep model rehydrates from the store rather than from anything in memory).

Every exit path converges back to a serving cortex, leaves the record in a terminal state, and
says what happened on the turn's own stream. ADR-0030 decision 4 and
``docs/modules/brain-core.md`` give the step order and what a failure at each step costs; the
ordering constraints that the code does not show are commented where they apply below.

A failure of the sequence itself settles with an app-authored reason (``swap_reasons.py``), and
the two that arrive as an exception settle with that exception's own message, which is how the
model host's message reaches the brain's side. What the user is told is separate: the notes
describe the GPU rather than the fault.

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
from cortex_core.swap_reasons import DRAIN_TIMEOUT_REASON, TORN_DOWN_REASON
from cortex_core.swap_settle import HandoffSettler

_logger = logging.getLogger(__name__)


def _status(detail: str) -> StatusUpdate:
    """One swap-window progress event, under the state the overlay renders as a chip."""
    return StatusUpdate(state=SWAPPING_STATE, detail=detail)


class SwapConductor:
    """Runs one brain handoff end to end, as a stream of events for the escalating turn.

    ``scheduler`` is ``None`` with no subagent pool, and a ``coresident`` plan takes down no tier
    the pool feeds, so neither owes a drain: there is nothing to quiesce. Everything else is
    required, and every collaborator is a port, so the sequence runs over fakes.
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
        Whether the handoff happened is reported on the stream, never raised at the caller,
        except when the turn itself is being torn down.

        The claim wraps everything, so a handoff that loses it has drained nothing and evicted
        nothing, and the sequence below runs only for the one turn that owns the GPU.
        """
        try:
            async with self._residency.handoff_claim():
                run = self._run_claimed(slot, session_id=session_id, turn_id=turn_id)
                try:
                    async for event in run:
                        yield event
                finally:
                    # Deterministic teardown, as for every other generator here: a consumer that
                    # stops iterating must unwind the sequence rather than leave it to the
                    # garbage collector.
                    await run.aclose()
        except HandoffInProgressError:
            _logger.warning(
                "refusing a handoff while another one holds the swap",
                extra={"session_id": session_id, "turn_id": turn_id},
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
                # Nothing has been evicted at this point, so the cortex is still serving and the
                # turn ends with what it already has.
                await self._settle.fail(prepared, DRAIN_TIMEOUT_REASON)
                yield TextDelta(text=DRAIN_TIMEOUT_NOTE)
                return
            swap = self._swap(prepared)
            try:
                async for event in swap:
                    yield event
            finally:
                # Deterministic teardown of the inner generator: a consumer that closes this one
                # must unwind the residency scope rather than leave it to the garbage collector.
                # This close is also nested inside the undrain's ``finally``, which is what keeps
                # the drain window shut across the swap back: closing the swap restores the
                # standing residency, and only then may admission reopen. Hoisting the undrain
                # above this line would hand delegated work to a tier that is still stopped.
                await swap.aclose()
        except BaseException:
            # Cancellation and stream teardown included: a handoff that stops being run is a
            # failed handoff, and a live record would otherwise strand the next boot. The write is
            # best-effort under cancellation, and boot recovery is the backup for it.
            await self._settle.fail(prepared, TORN_DOWN_REASON)
            raise
        finally:
            # Admission reopens here and nowhere else. This runs on every path (a drain that timed
            # out, a swap that failed, a clean handoff, a teardown) and it runs last, after the
            # swap generator above has been closed and has therefore restored the standing
            # residency.
            self._undrain()

    async def _prepare(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> HandoffRecord | str:
        """Serialize the slot into a ``READY`` record, or the note saying why there is none."""
        if slot.refs is not None and slot.refs.taint.opaque:
            # Pixels are turn-local (ADR-0029 decision 6): no store persists them, so the deep
            # model would get a tool message promising a picture with none attached. Keyed on the
            # ``opaque`` bit, which stays true wherever the pixels cannot travel.
            _logger.warning(
                "refusing a handoff for a turn that read the screen",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            return OPAQUE_TURN_NOTE
        deep = self._plan.brain_model
        if await self._residency.unhosted(deep):
            # Checked here, before the store is touched and long before the drain: this
            # deployment's host carries no such tier, so the start inside the residency scope
            # would fail with the cortex already unloaded. Asked every time rather than cached,
            # because the daemon that answers can be replaced by one whose roster was fixed, and
            # a cached answer would keep failing a deployment that now works.
            _logger.error(
                "escalation was asked for but the model host does not serve the deep model, so "
                "the handoff was refused with nothing drained and nothing unloaded: name an "
                "artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or turn escalation off "
                "(CORTEX_ESCALATION)",
                extra={"model": deep, "session_id": session_id, "turn_id": turn_id},
            )
            return UNHOSTED_TIER_NOTE
        try:
            if (active := await self._handoffs.active()) is not None:
                # The claim already rejected anything racing this turn in this process, so a
                # record still live here is one the store kept: a settle that never landed, or a
                # handoff another process owns. Either way this turn evicts nothing. Two turn ids
                # appear on the line below, a handoff id being the escalating turn's id
                # (``handoff.py``), so the one the store is holding gets the qualified field name
                # and this turn keeps the plain one (ADR-0009 sixth-name addendum). Only this
                # turn's conversation is named: the held handoff's chat is on its own lines,
                # reached by the id here (ADR-0009 named-conversation addendum).
                held = active.handoff_id
                _logger.warning(
                    "refusing a handoff while the store still has one in flight",
                    extra={"active_turn_id": held, "session_id": session_id, "turn_id": turn_id},
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

        A handoff killed at this exact boundary would otherwise strand a non-terminal record that
        ``active()`` keeps answering with, and every later escalation would be rejected as a second
        concurrent handoff until the next restart. The teardown paths therefore fail the record
        here too, while the object still exists to be failed.
        """
        try:
            await self._handoffs.put(record)
        except HandoffStoreError:
            _logger.exception("the handoff store failed before anything was evicted")
            return STORE_FAILED_NOTE
        except BaseException:
            await self._settle.fail(record, TORN_DOWN_REASON)
            raise
        return record

    async def _swap(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Swap in, run the deep model's phase, swap back, and settle the record."""
        try:
            yield _status(LOADING_DETAIL)
            async with self._residency.swap_scope(self._plan.brain_model):
                # Only now is the deep model actually serving: the record reaches BRAIN_ACTIVE
                # after the health gate passed, never on the strength of a start call alone.
                await self._settle.advance(record, HandoffState.BRAIN_ACTIVE)
                yield _status(WORKING_DETAIL)
                phase = self._brain_phase.run(record)
                try:
                    async for event in phase:
                        yield event
                finally:
                    await phase.aclose()
                yield _status(RESTORING_DETAIL)
        except InferenceError as err:
            # The deep model died mid-work. Its phase has already streamed and persisted the
            # partial answer with a note saying it is unfinished, so the scope's ``finally`` has
            # restored the cortex and only the record is left to settle. The record keeps the
            # server's own message, which that note does not carry.
            await self._settle.fail(record, str(err))
            return
        except ModelManagerError as err:
            # This error's message carries the model host's status code and the leading characters
            # of its response body, which is the only way either reaches the record. The note
            # streamed below describes the GPU instead, and says none of that to the user.
            await self._settle.fail(record, str(err))
            yield TextDelta(text=note_for(err))
            return
        await self._settle.advance(record, HandoffState.DONE)

    async def _drain(self) -> bool:
        """Quiesce the pool; return True when there is no pool, or no tier to quiesce it for."""
        if self._scheduler is None or self._plan.coresident:
            return True
        return await self._scheduler.drain(timeout_s=self._plan.drain_timeout_s)

    def _undrain(self) -> None:
        """Resume admission, whatever ended the handoff (the drain window is never leaked)."""
        if self._scheduler is not None:
            self._scheduler.undrain()
