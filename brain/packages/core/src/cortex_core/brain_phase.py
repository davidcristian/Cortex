"""The deep model's half of a handoff: rehydrate from the record, run, persist (ADR-0030 d4).

Steps 4 and 5 of the swap sequence, as a use-case of its own, and the one hard rule made
executable: every input comes back out of a store or the handoff record, nothing from the process
that ran the cortex phase, so a different process on a different set of weights continues the same
turn. ``docs/modules/brain-core.md`` lists what is rebuilt and from where.

It is also the only caller that watches decode cadence (ADR-0030 spill-watch addendum). A handoff
that overcommitted the card still succeeds: both tiers report ``ready``, the fit check passed on a
declared cost that was too low or on room the desktop took during the load, and the driver pages
the excess to host memory rather than failing the load, so throughput is the only remaining
witness. The reply is already streaming by the time the rate is known, so the phase reports what
it measured once per handoff and changes nothing else about the turn. The verdict goes to the log
and to the ``PaceSink`` this phase was wired with (ADR-0030 spill-note addendum), the sink being
how a spill reaches an operator who is not tailing a container.
"""

import logging
from collections.abc import AsyncGenerator, Sequence

from cortex_core.cadence import NO_CADENCE_TERMS, CadenceReading, CadenceTerms, CadenceWatch
from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError
from cortex_core.events import TextDelta, TurnEvent
from cortex_core.handoff import HandoffRecord
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.stops import StopLedger
from cortex_core.swap_notes import BRAIN_FAILED_NOTE
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import cap_note, flush_channels, record_exchange, stream_turn_events
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
        cadence: CadenceTerms = NO_CADENCE_TERMS,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._model = brain_model
        self._caps = capabilities
        # The deep tier's decode rate on this deployment's own card, measured by the deployment
        # exactly as its VRAM cost was and just as unknowable from inside a container, plus the
        # sink that verdict is published to. Zero (the default, and every deployment that has not
        # measured one) reports the rate and judges nothing, which is why the watch exists either
        # way: the healthy number is what makes a later collapse readable, and it is the same
        # instrument that publishes both.
        self._cadence = cadence

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
        watch = CadenceWatch(self._cadence.floor_tps)
        # The deep tier is where a cut answer is likeliest and least visible: it ships an 8192
        # context and the measured pick spends 3847 to 4448 tokens reaching an answer, so the
        # wall is one long question away even with no cap set (ADR-0004 brain-pick table).
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
            # No slot: the deep model cannot escalate to itself, and the built-in refuses
            # honestly rather than queuing a handoff no conductor would run.
            escalation=None,
            cadence=watch,
            stops=stops,
            # The cortex turn's own bounds, carried on the same bundle (ADR-0005 capped-reply
            # addendum): a handoff is one turn continued, so a deployment that capped a reply did
            # not ask for the cap to lapse the moment the question got hard enough to escalate.
            bounds=self._caps.bounds,
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
        # Only when the phase itself did not fail. ``BRAIN_FAILED_NOTE`` already says this answer
        # is unfinished and names the likelier cause, so a second note under it would offer the
        # reader two explanations for one stump, one of them about a limit that may not be what
        # ended the run at all.
        if failure is None:
            for event in cap_note(stops, parts):
                yield event
        self._report_cadence(watch.reading(), record)
        await self._persist(record, query=query, reply="".join(parts), taint=taint)
        if failure is not None:
            raise failure

    def _report_cadence(self, reading: CadenceReading | None, record: HandoffRecord) -> None:
        """Say what the deep tier's throughput was, once, after the phase and before it persists.

        Placed after the stream rather than inside it so the whole handoff's completions are in
        hand: a tool loop runs several, and the question is about the tier across all of them.
        Placed before ``_persist`` so a failed phase, which re-raises after persisting, still
        reports what it managed to observe. Both lines name the work ``turn_id``, the handoff id
        they are handed being the escalating turn's own (ADR-0009 sixth-name addendum), so a
        slow deep tier is joined to that turn's other lines by the field they all share.

        Both name the **conversation** as well, which is the one field here that is arguably about
        something else: the rate is a fact about the card. It is attached anyway, because these
        are the only lines a handoff that *worked* ever writes, every refusal and every settle
        above being a failure path, so without it a chat that escalated successfully and decoded
        slowly has no swap-path evidence a reader can reach at all (ADR-0009 named-conversation
        addendum). The deployment-wide reading of the same measurement has its own destination
        and carries no chat: ``_note_pace`` below publishes it to the residency record.
        """
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
            "tokens_per_second": reading.observed.tokens_per_second,
            "tokens": reading.observed.tokens,
            "floor_tokens_per_second": reading.floor,
            "samples": reading.samples,
            "judged": reading.judged,
        }
        if reading.collapsed:
            _logger.warning(SPILLED_LOG_MSG, extra=extra | {"shortfall": reading.shortfall})
        else:
            _logger.info(_MEASURED_LOG_MSG, extra=extra)
        self._note_pace(reading)

    def _note_pace(self, reading: CadenceReading) -> None:
        """Publish the verdict past the log, when there is one and somewhere to publish it.

        After the log rather than before it, so a sink that somehow misbehaves cannot cost the
        line this watch has always written. Two things make this nothing at all: a
        deployment that wired no sink, which is every one that ran before the note existed, and a
        deployment that declared no floor, whose reading is a number and not a judgement. The
        second is why ``verdict`` is asked rather than ``collapsed``: a "no" for want of anything
        to compare against would clear a standing note as firmly as a real one.
        """
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
