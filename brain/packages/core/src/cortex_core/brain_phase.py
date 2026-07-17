"""The deep model's half of a handoff: rehydrate from the record, run, persist (ADR-0030 d4)."""

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
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._model = brain_model
        self._caps = capabilities

    async def run(self, record: HandoffRecord) -> AsyncGenerator[TurnEvent, None]:
        """Rehydrate, run the shared tool loop on the deep model, persist, and stream it out."""
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
