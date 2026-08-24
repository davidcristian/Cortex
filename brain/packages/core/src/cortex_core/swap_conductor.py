"""The swap sequence: serialize, drain, swap, run, persist, swap back (ADR-0030 decision 4)."""

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
        self._settle = HandoffSettler(handoffs)

    async def run_handoff(
        self, slot: EscalationSlot, *, session_id: str, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run the whole sequence for one filled slot, streaming status, text, and notes."""
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
                "refusing a handoff while another one holds the swap", extra={"turn_id": turn_id}
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
                await self._settle.fail(prepared, DRAIN_TIMEOUT_REASON)
                yield TextDelta(text=DRAIN_TIMEOUT_NOTE)
                return
            swap = self._swap(prepared)
            try:
                async for event in swap:
                    yield event
            finally:
                await swap.aclose()
        except BaseException:
            # Cancellation and stream teardown included: a handoff that stops being run is a
            # failed handoff, and a live record would otherwise strand the next boot. The write
            # is best-effort under cancellation, which is exactly what boot recovery backs up.
            await self._settle.fail(prepared, TORN_DOWN_REASON)
            raise
        finally:
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
                "refusing a handoff for a turn that read the screen", extra={"turn_id": turn_id}
            )
            return OPAQUE_TURN_NOTE
        if await self._residency.unhosted(self._plan.brain_model):
            _logger.error(
                "escalation was asked for but the model host does not serve the deep model, so "
                "the handoff was refused with nothing drained and nothing unloaded: name an "
                "artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or turn escalation off "
                "(CORTEX_ESCALATION)",
                extra={"model": self._plan.brain_model, "turn_id": turn_id},
            )
            return UNHOSTED_TIER_NOTE
        try:
            if (active := await self._handoffs.active()) is not None:
                _logger.warning(
                    "refusing a handoff while the store still has one in flight",
                    extra={"active_turn_id": active.handoff_id, "turn_id": turn_id},
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
            await self._settle.fail(record, TORN_DOWN_REASON)
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
        except InferenceError as err:
            await self._settle.fail(record, str(err))
            return
        except ModelManagerError as err:
            # The one path this whole field exists for: the error's message is where the model
            # host's status code and the leading characters of its own response body ended up,
            # and the note below is about the GPU rather than about any of that.
            await self._settle.fail(record, str(err))
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
