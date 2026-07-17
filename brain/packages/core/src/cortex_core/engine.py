"""Handle one user turn: pure orchestration over the ports, no I/O of its own."""

from collections.abc import AsyncGenerator, Callable, Mapping
from uuid import uuid4

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError
from cortex_core.events import TextDelta, ToolActivity, TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationRefs
from cortex_core.loop_events import ReasoningDelta, ToolStep
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.session_title import build_title_messages, generate_title
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.untrusted import TaintLedger, new_nonce

# The logical id of the resident cortex model (ADR-0004: logical ids, never paths).
# Deployments override it via CORTEX_MODEL_CORTEX, which is read by the composition root
# (the orchestrator), never by the core.
DEFAULT_CORTEX_MODEL = "cortex"


def _uuid4_turn_id() -> str:
    """Default turn-id factory; injectable so tests can pin ids."""
    return str(uuid4())


def _render_exchange(user_text: str, assistant_text: str) -> str:
    """Render one completed turn as the memory recorded at turn end (ADR-0008)."""
    return f"User: {user_text}\nAssistant: {assistant_text}"


def _arm_escalation(
    caps: TurnCapabilities, working: list[Message], context: ToolLoopContext
) -> None:
    """Arm the turn's escalation slot at turn start, when one is handed in (ADR-0030)."""
    if caps.escalation is None:
        return
    caps.escalation.refs = EscalationRefs(
        working=working,
        taint=context.taint,
        nonce=context.nonce,
        budget=context.budget,
        base_len=len(working),
    )


class TurnEngine:
    """The "handle a user turn" use-case, wired only to ports."""

    def __init__(
        self,
        store: SessionStore,
        backend: InferenceBackend,
        clock: Clock,
        *,
        cortex_model: str = DEFAULT_CORTEX_MODEL,
        capabilities: TurnCapabilities | None = None,
        turn_id_factory: Callable[[], str] = _uuid4_turn_id,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._caps = capabilities if capabilities is not None else TurnCapabilities()
        self._turn_id_factory = turn_id_factory
        # Model choice is keyed off the routed tier. Only the cortex tier is servable
        # in Slice 3 (route_turn with default hints always selects it); subagent and
        # brain entries join the map when the ModelManager lands (Slices 4/7).
        self._model_by_tier: Mapping[Tier, str] = {Tier.CORTEX: cortex_model}

    async def handle_turn(self, session_id: str, text: str) -> AsyncGenerator[TurnEvent, None]:
        """Persist the user turn, recall memory, run the inference↔tool loop, then persist
        the reply and record the exchange to memory on completion."""
        model = self._model_by_tier[route_turn(RoutingHints())]
        turn_id = self._turn_id_factory()
        user = Message(role=Role.USER, text=text, at=self._clock.now(), turn_id=turn_id)
        await self._store.append(session_id, user)
        history = await self._store.history(session_id)
        # Build the loop context first: recall may fence a tainted memory (ADR-0019) with the same
        # per-turn nonce the tool loop uses and taint the turn before it runs, so the ledger and
        # nonce must exist before the messages are assembled.
        taint = TaintLedger()
        context = ToolLoopContext(
            dispatcher=self._caps.tools,
            clock=self._clock,
            turn_id=turn_id,
            taint=taint,
            nonce=new_nonce(),
            session_id=session_id,
            # This stream's progress channel (ADR-0010): the loop stamps it onto each dispatch,
            # so a spawned subagent surfaces its steps while handle_turn is suspended inside the
            # spawn dispatch and cannot yield an event of its own.
            progress=self._caps.progress,
            # This turn's handoff slot (ADR-0030): the loop stamps it onto each dispatch so
            # the escalate built-in can write the brief; armed with the turn's refs below,
            # once the working list exists.
            escalation=self._caps.escalation,
        )
        working = list(
            await assemble_inference_messages(text, history, self._caps, context, self._clock)
        )
        # Arm the escalation slot, if any, at the loop boundary's start (ADR-0030 decision 2).
        _arm_escalation(self._caps, working, context)
        parts: list[str] = []
        guard, thinking = open_output_channels(self._caps.guardrail, taint, text)
        loop = stream_tool_loop(self._backend, model, working, context)
        try:
            async for delta in loop:
                if isinstance(delta, ReasoningDelta):
                    if (status := thinking.feed(delta.text)) is not None:
                        yield status
                    continue
                if isinstance(delta, ToolStep):
                    # An audited dispatch about to run (ADR-0009 addendum): surfaced as ephemeral
                    # activity for the overlay chip, with the same non-reply treatment.
                    yield ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
                    continue
                shown = delta if guard is None else guard.feed(delta)
                if not shown:
                    continue
                parts.append(shown)
                yield TextDelta(text=shown)
        finally:
            # A consumer that closes this generator mid-turn must not leave the shared loop
            # (and the backend stream it holds) half-suspended. Close it deterministically.
            await loop.aclose()
        if (status := thinking.release()) is not None:
            # The trace's one flush: end of stream releases the scrubbed thinking carry,
            # which deliberately survived any burst boundaries (see ThinkingChannel).
            yield status
        if guard is not None and (tail := guard.flush()):
            parts.append(tail)
            yield TextDelta(text=tail)
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT, text=full_text, at=self._clock.now(), turn_id=turn_id
        )
        await self._store.append(session_id, assistant)
        # A turn that read untrusted content is dropped from memory by default (ADR-0013), so every
        # stored memory comes from an untainted turn. With record_tainted_memory on (ADR-0019) it is
        # recorded instead with the untrusted-provenance marker, so recall fences it as data.
        if self._caps.memory is not None and (
            not taint.tainted or self._caps.record_tainted_memory
        ):
            await self._caps.memory.record(
                _render_exchange(text, full_text), session_id=session_id, tainted=taint.tainted
            )
        if self._caps.generate_titles and len(history) == 1:
            await self._title_session(session_id, model, text, full_text, turn_id)
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)

    async def _title_session(
        self, session_id: str, model: str, user_text: str, assistant_text: str, turn_id: str
    ) -> None:
        """Generate a switcher title from the opening exchange and persist it (ADR-0021)."""
        try:
            title = await generate_title(
                self._backend,
                model,
                build_title_messages(
                    user_text, assistant_text, at=self._clock.now(), turn_id=turn_id
                ),
            )
        except InferenceError:
            return
        if title:
            await self._store.set_title(session_id, title)
