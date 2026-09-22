"""The deep model's half of a handoff: rehydrate from the record, run, then persist."""

import logging
from collections.abc import AsyncGenerator, Sequence

from cortex_core.cadence import NO_CADENCE_TERMS, CadenceReading, CadenceTerms, CadenceWatch
from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError, MalformedToolCallError
from cortex_core.events import TextDelta, TurnEvent
from cortex_core.handoff import HandoffRecord
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.stops import StopLedger
from cortex_core.swap_notes import BRAIN_FAILED_NOTE, WORKING_DETAIL
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import (
    cap_note,
    flush_channels,
    record_exchange,
    stream_turn_events,
    unreadable_call_note,
)
from cortex_core.untrusted import TaintLedger
from cortex_core.waits import THINKING, Wait

_logger = logging.getLogger(__name__)

SPILLED_LOG_MSG = (
    "the deep model decoded below the rate this deployment measured for it, which is what an "
    "overcommitted card looks like: the load was not refused, it was paged to host memory"
)
_MEASURED_LOG_MSG = "the deep model's decode rate for this handoff"
_NO_READING_LOG_MSG = (
    "no decode rate was reported for this handoff, so nothing was checked; a completion too "
    "short to judge, a failed phase, or a backend whose engine reports no timings all read alike"
)
_UNREADABLE_CALL_LOG_MSG = (
    "a tool call the deep model wrote could not be read; ending this handoff where it broke"
)
_DEEP_GENERATING = Wait(THINKING, WORKING_DETAIL)


def _user_query(history: Sequence[Message], record: HandoffRecord) -> str:
    """What this turn asked, recovered from the store for recall and the memory record."""
    for message in reversed(history):
        if message.role is Role.USER and message.turn_id == record.handoff_id:
            return message.text
    return record.brief


class BrainPhase:
    """Runs one handoff record on the deep model and persists what it produced."""

    def __init__(
        self,
        store: SessionStore,
        backend: InferenceBackend,
        clock: Clock,
        brain_model: str,
        capabilities: TurnCapabilities,
        cadence: CadenceTerms = NO_CADENCE_TERMS,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._model = brain_model
        self._caps = capabilities
        self._cadence = cadence

    async def run(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Rehydrate, run the shared tool loop on the deep model, persist, and stream it out."""
        history = await self._store.history(record.session_id)
        query = _user_query(history, record)
        taint = record.taint_ledger()
        watch = CadenceWatch(self._cadence.floor_tps)
        stops = StopLedger()
        context = ToolLoopContext(
            dispatcher=self._caps.tools,
            clock=self._clock,
            turn_id=record.handoff_id,
            taint=taint,
            nonce=record.nonce,
            session_id=record.session_id,
            budget=DispatchBudget.resume(
                remaining=record.budget_remaining, closed=record.budget_closed
            ),
            progress=self._caps.progress,
            escalation=None,
            cadence=watch,
            stops=stops,
            bounds=self._caps.bounds,
            generating=_DEEP_GENERATING,
        )
        assembled = await assemble_inference_messages(
            query, history, self._caps, context, self._clock
        )
        working = [*assembled, *record.loop_tail]
        channels = open_output_channels(self._caps.guardrail, taint, query)
        parts: list[str] = []
        failure: InferenceError | None = None
        events = stream_turn_events(
            stream_tool_loop(self._backend, self._model, working, context), channels, parts
        )
        try:
            async for event in events:
                yield event
        # ``MalformedToolCallError`` subclasses ``InferenceError``, so it is caught first.
        except MalformedToolCallError:
            _logger.warning(
                _UNREADABLE_CALL_LOG_MSG,
                extra={
                    "model": self._model,
                    "session_id": record.session_id,
                    "turn_id": record.handoff_id,
                    "capped": stops.capped,
                },
                exc_info=True,
            )
            # ``stream_turn_events`` flushes only on a clean end, so this path flushes.
            for held in flush_channels(channels, parts):
                yield held
            for event in unreadable_call_note(stops, parts):
                yield event
        except InferenceError as err:
            failure = err
            for held in flush_channels(channels, parts):
                yield held
            parts.append(BRAIN_FAILED_NOTE)
            yield TextDelta(text=BRAIN_FAILED_NOTE)
        finally:
            await events.aclose()
        if failure is None:
            for event in cap_note(stops, parts):
                yield event
        self._report_cadence(watch.reading(), record)
        await self._persist(record, query=query, reply="".join(parts), taint=taint)
        if failure is not None:
            raise failure

    def _report_cadence(self, reading: CadenceReading | None, record: HandoffRecord) -> None:
        """Log the deep tier's throughput once, after the phase and before it persists."""
        if reading is None:
            _logger.info(
                _NO_READING_LOG_MSG,
                extra={
                    "model": self._model,
                    "session_id": record.session_id,
                    "turn_id": record.handoff_id,
                },
            )
            return
        extra = {
            "model": self._model,
            "session_id": record.session_id,
            "turn_id": record.handoff_id,
            "decode_rate": reading.observed.tokens_per_second,
            "decoded": reading.observed.tokens,
            "floor_rate": reading.floor,
            "samples": reading.samples,
            "judged": reading.judged,
        }
        if reading.collapsed:
            _logger.warning(SPILLED_LOG_MSG, extra=extra | {"shortfall": reading.shortfall})
        else:
            _logger.info(_MEASURED_LOG_MSG, extra=extra)
        self._note_pace(reading)

    def _note_pace(self, reading: CadenceReading) -> None:
        """Report the result past the log, when there is one and a sink to report it to."""
        if self._cadence.sink is not None and reading.verdict is not None:
            self._cadence.sink.note_pace(spilled=reading.verdict)

    async def _persist(
        self, record: HandoffRecord, *, query: str, reply: str, taint: TaintLedger
    ) -> None:
        """Append the deep model's reply and record the exchange under the turn's taint policy."""
        message = Message(
            role=Role.ASSISTANT, text=reply, at=self._clock.now(), turn_id=record.handoff_id
        )
        await self._store.append(record.session_id, message)
        await record_exchange(
            self._caps, taint, session_id=record.session_id, query=query, reply=reply
        )
