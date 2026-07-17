"""The swap sequence: serialize, drain, swap, run, persist, swap back (ADR-0030 decision 4)."""

import logging
from collections.abc import AsyncGenerator

from cortex_core.brain_phase import BrainPhase
from cortex_core.errors import (
    HandoffStoreError,
    InferenceError,
    ModelManagerError,
    ResidencyRestoreError,
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
    RESTORE_FAILED_NOTE,
    RESTORING_DETAIL,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    WORKING_DETAIL,
)

_logger = logging.getLogger(__name__)


def _status(detail: str) -> StatusUpdate:
    """One swap-window progress event, under the state the overlay renders as a chip."""
    return StatusUpdate(state=SWAPPING_STATE, detail=detail)


class SwapConductor:
    """Runs one brain handoff end to end, as a stream of events for the escalating turn."""

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

    async def run_handoff(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run the whole sequence for one filled slot, streaming status, text, and notes."""
        prepared = await self._prepare(slot, session_id=session_id, turn_id=turn_id)
        if isinstance(prepared, str):
            yield TextDelta(text=prepared)
            return
        try:
            yield _status(DRAINING_DETAIL)
            if not await self._drain():
                # The abort direction: nothing has been evicted, so the cortex is still serving
                # and the turn simply ends with what it has.
                await self._advance(prepared, HandoffState.FAILED)
                yield TextDelta(text=DRAIN_TIMEOUT_NOTE)
                return
            swap = self._swap(prepared)
            try:
                async for event in swap:
                    yield event
            finally:
                # Deterministic teardown of the inner generator: a consumer that closes this
                # one must unwind the residency scope, not abandon it to the garbage collector.
                await swap.aclose()
        except BaseException:
            # Cancellation and stream teardown included: a handoff that stops being run is a
            # failed handoff, and a live record would otherwise strand the next boot. The write
            # is best-effort under cancellation, which is exactly what boot recovery backs up.
            await self._advance(prepared, HandoffState.FAILED)
            raise
        finally:
            self._undrain()

    async def _prepare(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> HandoffRecord | str:
        """Serialize the slot into a ``READY`` record, or the note saying why there is none."""
        try:
            if (active := await self._handoffs.active()) is not None:
                _logger.warning(
                    "refusing a second concurrent handoff",
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
        """Write the ``READY`` record, and never leave it live if the write is interrupted."""
        try:
            await self._handoffs.put(record)
        except HandoffStoreError:
            _logger.exception("the handoff store failed before anything was evicted")
            return STORE_FAILED_NOTE
        except BaseException:
            await self._advance(record, HandoffState.FAILED)
            raise
        return record

    async def _swap(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Swap in, run the deep model's phase, swap back, and settle the record."""
        try:
            yield _status(LOADING_DETAIL)
            async with self._residency.swap_scope(self._plan.brain_model):
                # Only now is the deep model actually serving: the record reaches BRAIN_ACTIVE
                # after the health gate passed, never on the strength of a start call.
                await self._advance(record, HandoffState.BRAIN_ACTIVE)
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
            await self._advance(record, HandoffState.FAILED)
            return
        except ModelManagerError as err:
            await self._advance(record, HandoffState.FAILED)
            yield TextDelta(text=_note_for(err))
            return
        await self._advance(record, HandoffState.DONE)

    async def _drain(self) -> bool:
        """Quiesce the subagent pool, or answer True when there is no pool to quiesce."""
        if self._scheduler is None:
            return True
        return await self._scheduler.drain(timeout_s=self._plan.drain_timeout_s)

    def _undrain(self) -> None:
        """Resume admission, whatever ended the handoff (the drain window is never leaked)."""
        if self._scheduler is not None:
            self._scheduler.undrain()

    async def _advance(self, record: HandoffRecord, state: HandoffState) -> None:
        """Move the record to ``state``, deleting a completed one; never raises.

        A store that fails here must not turn a converged swap into a crash, so the failure is
        logged and left to boot recovery, which marks any non-terminal record ``FAILED``.
        """
        try:
            await self._handoffs.transition(record.handoff_id, state)
            if state is HandoffState.DONE:
                await self._handoffs.delete(record.handoff_id)
        except HandoffStoreError:
            _logger.exception(
                "could not record the handoff's state",
                extra={"handoff": record.handoff_id, "state": state.value},
            )


def _note_for(error: ModelManagerError) -> str:
    """The honest note for a swap that broke: the GPU serves nothing, or it serves the cortex.

    A failed restore is the graver statement (the next turn may fail too), and it wins even
    when it happened while unwinding some other failure, because it is what is true now.
    """
    if isinstance(error, ResidencyRestoreError):
        return RESTORE_FAILED_NOTE
    return SWAP_FAILED_NOTE
