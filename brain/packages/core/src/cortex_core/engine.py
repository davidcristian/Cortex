"""Handle one user turn: pure orchestration over the ports, no I/O of its own."""

import logging
from collections.abc import AsyncGenerator, Mapping

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError, MalformedToolCallError
from cortex_core.events import TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationRefs
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.session_title import build_title_messages, generate_title
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import (
    cap_note,
    flush_channels,
    record_exchange,
    stream_turn_events,
    unreadable_call_note,
)
from cortex_core.untrusted import TaintLedger, new_nonce

_logger = logging.getLogger(__name__)

# Deployments override this with CORTEX_MODEL_CORTEX, read by the orchestrator, not the core.
DEFAULT_CORTEX_MODEL = "cortex"


def _arm_escalation(
    caps: TurnCapabilities, working: list[Message], context: ToolLoopContext
) -> None:
    """Set up the turn's escalation slot at turn start, when the caller provided one."""
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
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._caps = capabilities if capabilities is not None else TurnCapabilities()
        self._model_by_tier: Mapping[Tier, str] = {Tier.CORTEX: cortex_model}

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Persist the user turn, run the inference and tool loop, then persist the reply."""
        model = self._model_by_tier[route_turn(RoutingHints())]
        user = Message(role=Role.USER, text=text, at=self._clock.now(), turn_id=turn_id)
        await self._store.append(session_id, user)
        history = await self._store.history(session_id)
        taint = TaintLedger()
        stops = StopLedger()
        context = ToolLoopContext(
            dispatcher=self._caps.tools,
            clock=self._clock,
            turn_id=turn_id,
            taint=taint,
            nonce=new_nonce(),
            session_id=session_id,
            bounds=self._caps.bounds,
            stops=stops,
            progress=self._caps.progress,
            escalation=self._caps.escalation,
        )
        working = list(
            await assemble_inference_messages(text, history, self._caps, context, self._clock)
        )
        _arm_escalation(self._caps, working, context)
        parts: list[str] = []
        channels = open_output_channels(self._caps.guardrail, taint, text)
        loop = stream_tool_loop(self._backend, model, working, context)
        events = stream_turn_events(loop, channels, parts)
        try:
            async for event in events:
                yield event
        except MalformedToolCallError:
            _logger.warning(
                "a tool call the model wrote could not be read; ending this turn where it broke",
                extra={"session_id": session_id, "turn_id": turn_id, "capped": stops.capped},
                exc_info=True,
            )
            # ``stream_turn_events`` flushes only on a clean end, so this path flushes.
            for held in flush_channels(channels, parts):
                yield held
            for event in unreadable_call_note(stops, parts):
                yield event
        finally:
            await events.aclose()
        # After the channels flush and before the text is joined, so the note comes under the
        # whole reply and what is saved is what was shown.
        for event in cap_note(stops, parts):
            yield event
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT, text=full_text, at=self._clock.now(), turn_id=turn_id
        )
        await self._store.append(session_id, assistant)
        await record_exchange(self._caps, taint, session_id=session_id, query=text, reply=full_text)
        # Before ``TurnCompleted``, so the overlay's refresh on completion already sees the title.
        if self._caps.generate_titles and len(history) == 1:
            await self._title_session(session_id, model, text, full_text, turn_id)
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)

    async def _title_session(
        self, session_id: str, model: str, user_text: str, assistant_text: str, turn_id: str
    ) -> None:
        """Generate a switcher title from the opening exchange and persist it."""
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
