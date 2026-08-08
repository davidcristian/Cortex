"""The deep model's half of a handoff: rehydrate from the record, run, persist (ADR-0030 d4).

Steps 4 and 5 of the swap sequence, as a use-case of its own. It is the one hard rule made
executable: every input it needs comes back out of a store or the handoff record, nothing from
the process that ran the cortex phase, so the model that answers is a different process on a
different set of weights and the turn still continues.

What is rebuilt, and from where:

- **history** from ``SessionStore`` (windowed as usual), which already holds the user message
  and the cortex's wrap-up;
- **the working set** as preamble + recalled context + history + the record's ``loop_tail``,
  the tail being the tool-call and fenced result messages the loop never persisted. The
  cortex's brief needs no separate carrier: it rides the tail as the arguments of the very
  ``escalate_to_brain`` call that asked for the handoff;
- **the taint ledger** from the record, so a tainted turn stays tainted across the swap (taint
  that did not survive would fail open) and the output guardrail opens over the same URL
  evidence the cortex collected;
- **the fence nonce** from the record, so the tail's fenced blocks stay explained by the
  preamble's markers-carry-a-random-id rule;
- **the dispatch budget** at its carried position, so a swap can never refill the turn's
  allowance. The rounds allowance is deliberately fresh (the budget is the spend bound and it
  carried; salience is per loop by design, so a cross-swap repeat costs budget but is not
  refused, a bounded residual ADR-0030 accepts).

The phase cannot escalate to itself: it runs with no escalation slot, so the built-in refuses
honestly if the deep model ever calls it. A mid-work failure (an ``InferenceError`` from a
server that died under it) persists the partial text with an honest note, the runner's
parts-so-far discipline, and then re-raises so the conductor marks the handoff failed and
converges back to the cortex.

**It is also where a spilled handoff is caught** (ADR-0030 spill-watch addendum). The fit check
inside ``swap_in`` reads free device memory immediately before the load, which is the only instant
that reading means anything, and two things stay invisible to it: a deployment that declared the
deep tier's cost too low, and memory the desktop took while the load ran. Both end in an
overcommit the driver pages to host memory rather than refusing, so both tiers report ``ready``
and the card reads like a fit. The one witness is throughput, and this phase is where a real
completion on the deep tier can be watched. It says so once per handoff and does nothing else to
the turn: the reply is already streaming by the time the rate is known, so refusing would spend a
user's answer on an operator's problem, and there is nothing left to degrade.
"""

import logging
from collections.abc import AsyncGenerator, Sequence

from cortex_core.cadence import CadenceReading, CadenceWatch
from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError
from cortex_core.events import TextDelta, TurnEvent
from cortex_core.handoff import HandoffRecord
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.swap_notes import BRAIN_FAILED_NOTE
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import flush_channels, record_exchange, stream_turn_events
from cortex_core.untrusted import TaintLedger

_logger = logging.getLogger(__name__)

# What the operator is told when the deep tier never reached the rate its deployment measured.
# One sentence naming the instrument, because the reader arriving at this line is arriving from a
# handoff that worked and was slow, and every other instrument they would reach for agrees it was
# fine (docs/runbooks/model-swap.md).
SPILLED_LOG_MSG = (
    "the deep model decoded below the rate this deployment measured for it, which is what an "
    "overcommitted card looks like: the load was not refused, it was paged to host memory"
)
_MEASURED_LOG_MSG = "the deep model's decode rate for this handoff"
_NO_READING_LOG_MSG = (
    "no decode rate was reported for this handoff, so nothing was checked; a completion too "
    "short to judge, a failed phase, or a backend whose engine reports no timings all read alike"
)


def _user_query(history: Sequence[Message], record: HandoffRecord) -> str:
    """What this turn asked, recovered from the store for recall and the memory record.

    The record carries no user text (it carries only what no store holds), so the query comes
    back out of history: the user message of the escalating turn. A session deleted mid-handoff
    leaves none, and the cortex's brief is then the truest available statement of the ask.
    """
    for message in reversed(history):
        if message.role is Role.USER and message.turn_id == record.handoff_id:
            return message.text
    return record.brief


class BrainPhase:
    """Runs one handoff record on the deep model and persists what it produced.

    ``capabilities`` is the bundle the cortex turn uses, with two things taken out at the
    composition root: the escalation slot (it cannot escalate to itself) and ``capture_screen``
    (ADR-0029: the tier that swaps in has no vision projector, and offering it eyes would spend
    the whole privacy cost of a screen read on a picture it cannot read). Same audit sink, same
    guardrail, same window, same memory policy otherwise. The deep model is not a different kind
    of citizen; it is the same turn, continued on other weights.
    """

    def __init__(
        self,
        store: SessionStore,
        backend: InferenceBackend,
        clock: Clock,
        brain_model: str,
        capabilities: TurnCapabilities,
        decode_floor_tps: float = 0.0,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._model = brain_model
        self._caps = capabilities
        # The deep tier's decode rate on this deployment's own card, measured by the deployment
        # exactly as its VRAM cost was and just as unknowable from inside a container. Zero (the
        # default, and every deployment that has not measured one) reports the rate and judges
        # nothing, which is why the watch exists either way: the healthy number is what makes a
        # later collapse readable, and it is the same instrument that publishes both.
        self._decode_floor_tps = decode_floor_tps

    async def run(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Rehydrate, run the shared tool loop on the deep model, persist, and stream it out.

        Yields the same event shapes the cortex phase does, so they ride the escalating turn's
        own stream as its continued deltas. The assistant message it persists is a **second**
        one under the same ``turn_id`` (ADR-0030 risk 4: history readers must not assume one
        reply per turn).
        """
        history = await self._store.history(record.session_id)
        query = _user_query(history, record)
        taint = record.taint_ledger()
        watch = CadenceWatch(self._decode_floor_tps)
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
            # No slot: the deep model cannot escalate to itself, and the built-in refuses
            # honestly rather than queuing a handoff no conductor would run.
            escalation=None,
            cadence=watch,
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
        except InferenceError as err:
            # The server died under the deep model. Keep what it produced, say so plainly, and
            # let the conductor converge; a partial answer with a note beats a silent loss.
            failure = err
            for held in flush_channels(channels, parts):
                yield held
            parts.append(BRAIN_FAILED_NOTE)
            yield TextDelta(text=BRAIN_FAILED_NOTE)
        finally:
            await events.aclose()
        self._report_cadence(watch.reading(), record.handoff_id)
        await self._persist(record, query=query, reply="".join(parts), taint=taint)
        if failure is not None:
            raise failure

    def _report_cadence(self, reading: CadenceReading | None, handoff_id: str) -> None:
        """Say what the deep tier's throughput was, once, after the phase and before it persists.

        Placed after the stream rather than inside it so the whole handoff's completions are in
        hand: a tool loop runs several, and the question is about the tier across all of them.
        Placed before ``_persist`` so a failed phase, which re-raises after persisting, still
        reports what it managed to observe.
        """
        if reading is None:
            _logger.info(_NO_READING_LOG_MSG, extra={"model": self._model, "handoff": handoff_id})
            return
        extra = {
            "model": self._model,
            "handoff": handoff_id,
            "tokens_per_second": reading.observed.tokens_per_second,
            "tokens": reading.observed.tokens,
            "floor_tokens_per_second": reading.floor,
            "samples": reading.samples,
            "judged": reading.judged,
        }
        if reading.collapsed:
            _logger.warning(SPILLED_LOG_MSG, extra=extra | {"shortfall": reading.shortfall})
            return
        _logger.info(_MEASURED_LOG_MSG, extra=extra)

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
