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
"""

from collections.abc import AsyncGenerator, Sequence

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

    ``capabilities`` is the same bundle the cortex turn uses, with the escalation slot left
    out at the composition root: same audited dispatcher, same guardrail, same window, same
    memory policy. The deep model is not a different kind of citizen; it is the same turn,
    continued on other weights.
    """

    def __init__(
        self,
        store: SessionStore,
        backend: InferenceBackend,
        clock: Clock,
        brain_model: str,
        capabilities: TurnCapabilities,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._model = brain_model
        self._caps = capabilities

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
        await self._persist(record, query=query, reply="".join(parts), taint=taint)
        if failure is not None:
            raise failure

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
