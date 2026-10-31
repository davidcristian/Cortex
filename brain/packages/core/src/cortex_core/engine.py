"""Handle one user turn: pure orchestration over the ports, no I/O of its own."""

import logging
from collections.abc import AsyncGenerator, Iterator, Mapping, Sequence

from cortex_core.attachments import (
    BLIND_ATTACHMENT_MSG,
    AttachmentError,
    attach_images,
    attachment_note,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.conversation import Message, Role
from cortex_core.errors import (
    SESSION_DELETED_MSG,
    ContextOverflowError,
    InferenceError,
    MalformedToolCallError,
    SessionDeletedError,
)
from cortex_core.events import TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationRefs
from cortex_core.handoff_wait import wait_out_handoff
from cortex_core.images import ImagePart
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.schedule_claim import said_by_person
from cortex_core.session_title import build_title_messages, generate_title
from cortex_core.shedding import shed_oldest_turns
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.tool_replay import RunLog
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import (
    OutputChannels,
    flush_channels,
    forget_unreadable,
    overflow_note,
    record_exchange,
    stream_turn_events,
    unreadable_call_note,
)
from cortex_core.untrusted import TaintLedger, new_nonce

_logger = logging.getLogger(__name__)

_UNREADABLE_CALL_LOG_MSG = (
    "a tool call the model wrote could not be read; ending this turn where it broke"
)
_OVERFLOW_LOG_MSG = "the prompt is longer than the model's context; ending this turn with a note"
_SHED_LOG_MSG = "the prompt is longer than the model's context; asking again without older turns"

# Deployments override this with CORTEX_MODEL_CORTEX, read by the orchestrator, not the core.
DEFAULT_CORTEX_MODEL = "cortex"


def _prepare_escalation(
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
        private_names=() if caps.tools is None else caps.tools.private_names,
    )


def _turn_taint(images: tuple[ImagePart, ...]) -> TaintLedger:
    """A fresh taint ledger, already tainted when the turn attaches images."""
    taint = TaintLedger()
    if images:
        taint.observe_attachment()
    return taint


def _shed(err: InferenceError, working: list[Message]) -> list[Message] | None:
    """The prompt to ask again with after a refusal, or ``None`` when the turn ends here."""
    if not isinstance(err, ContextOverflowError):
        return None
    return shed_oldest_turns(working, err.excess)


def _failure_log_msg(err: InferenceError, shed: list[Message] | None) -> str:
    """The warning for a stream that failed before the reply ended."""
    if shed is not None:
        return _SHED_LOG_MSG
    if isinstance(err, ContextOverflowError):
        return _OVERFLOW_LOG_MSG
    return _UNREADABLE_CALL_LOG_MSG


def _failure_ending(
    stops: StopLedger,
    channels: OutputChannels,
    parts: list[str],
    *,
    started: bool,
    err: InferenceError,
) -> Iterator[TurnEvent]:
    """Release what the channels hold, then the note that says why the turn ended there."""
    # ``stream_turn_events`` flushes only on a clean end, so this path flushes.
    yield from flush_channels(channels, parts)
    if isinstance(err, ContextOverflowError):
        yield from overflow_note(parts, alone=not started)
    else:
        yield from unreadable_call_note(stops, parts)


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
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent, None]:
        """Persist the user turn, run the inference and tool loop, then persist the reply."""
        model = self._model_by_tier[route_turn(RoutingHints())]
        if images:
            await self._refuse_blind(model)
        stored = text + attachment_note(images)
        user = Message(role=Role.USER, text=stored, at=self._clock.now(), turn_id=turn_id)
        await self._store.append(session_id, user)
        await self._wait_out_handoff(model)
        history = await self._history(session_id)
        taint = _turn_taint(images)
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
            query=text,
        )
        working = attach_images(
            await assemble_inference_messages(text, history, self._caps, context, self._clock),
            user,
            text=text,
            images=images,
        )
        parts: list[str] = []
        channels = open_output_channels(self._caps.guardrail, taint, text)
        overflowed = False
        log = RunLog()
        shed: list[Message] | None = working
        while shed is not None:
            working[:] = shed
            _prepare_escalation(self._caps, working, context)
            loop = stream_tool_loop(self._backend, model, working, context)
            events = stream_turn_events(loop, channels, parts, stops, text)
            started = False
            shed = None
            try:
                async for event in events:
                    started = True
                    yield log.note(event)
            except (MalformedToolCallError, ContextOverflowError) as err:
                # Before any output the prompt alone was refused, so older turns can be dropped.
                shed = None if started else _shed(err, working)
                overflowed = shed is None and isinstance(err, ContextOverflowError)
                taint.name_forget(forget_unreadable(err))
                _logger.warning(
                    _failure_log_msg(err, shed),
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "capped": stops.capped,
                        "dropped": 0 if shed is None else len(working) - len(shed),
                    },
                    exc_info=shed is None,
                )
                if shed is None:
                    for event in _failure_ending(stops, channels, parts, started=started, err=err):
                        yield event
            finally:
                await events.aclose()
        # After the channels flush and before the text is joined, so the note comes under the
        # whole reply and what is saved is what was shown.
        if not overflowed:
            notes = limit_notes(
                stops,
                log.runs,
                parts,
                caps=self._caps,
                taint=taint,
                query=text,
                said=said_by_person(history),
            )
            for event in notes:
                yield event
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT,
            text=full_text,
            at=self._clock.now(),
            turn_id=turn_id,
            runs=log.runs,
        )
        await self._store.append(session_id, assistant)
        await record_exchange(
            self._caps,
            taint,
            store=self._store,
            session_id=session_id,
            query=text,
            reply=full_text,
            runs=log.runs,
        )
        # Before ``TurnCompleted``, so the overlay's refresh on completion already sees the title.
        if len(history) == 1:
            await self._title_session(session_id, model, text, full_text, turn_id)
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)

    async def _history(self, session_id: str) -> Sequence[Message]:
        """The chat's history; raise ``SessionDeletedError`` when the chat was deleted."""
        history = await self._store.history(session_id)
        # Read after the history: a chat not yet deleted then still held this turn's message.
        if await self._store.deleted(session_id):
            raise SessionDeletedError(SESSION_DELETED_MSG)
        return history

    async def _refuse_blind(self, model: str) -> None:
        """Raise ``AttachmentError``, before anything is stored, when the model cannot see."""
        sight = self._caps.sight
        if sight is None:
            return
        # A handoff ahead has the cortex unloaded, and a probe asked then would answer no.
        await self._wait_out_handoff(model)
        if not await sight.can_see():
            raise AttachmentError(BLIND_ATTACHMENT_MSG)

    async def _wait_out_handoff(self, model: str) -> None:
        """Wait out a handoff already ahead, so the history read next includes what it stores."""
        if self._caps.residency is not None:
            await wait_out_handoff(self._caps.residency, self._caps.progress, model)

    async def _title_session(
        self, session_id: str, model: str, user_text: str, assistant_text: str, turn_id: str
    ) -> None:
        """Generate a switcher title from the opening exchange and persist it, when enabled."""
        if not self._caps.generate_titles:
            return
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
