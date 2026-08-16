"""Handle one user turn: pure orchestration over the ports, no I/O of its own.

The engine is a stateless function over the session store. Everything it knows
about a conversation is read back from ``SessionStore`` on every turn, so a process
restart or model swap between turns loses nothing (the one hard rule). Tool use adds an
in-turn loop (ADR-0009): the model may ask to run tools, the engine dispatches them, feeds
the results back, and re-infers until the model returns a final answer. That bounded loop
lives in ``tool_loop.py`` (shared with the subagent runner, ADR-0010); the turn's context
assembly and the ``TurnCapabilities`` bundle live in ``turn_context.py`` (the mechanical split
ADR-0029 decision 15 planned); the engine wraps the loop's text deltas as ``TextDelta`` events,
persists the assistant reply on completion, and arms the turn's ``EscalationSlot`` (ADR-0030)
when one is handed in, so the escalate tool and a later snapshot see exactly this turn's state.
"""

from collections.abc import AsyncGenerator, Callable, Mapping
from uuid import uuid4

from cortex_core.conversation import Message, Role
from cortex_core.errors import InferenceError
from cortex_core.events import TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationRefs
from cortex_core.output_channels import open_output_channels
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.session_title import build_title_messages, generate_title
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import TurnCapabilities, assemble_inference_messages
from cortex_core.turn_output import cap_note, record_exchange, stream_turn_events
from cortex_core.untrusted import TaintLedger, new_nonce

# The logical id of the resident cortex model (ADR-0004: logical ids, never paths).
# Deployments override it via CORTEX_MODEL_CORTEX, which is read by the composition root
# (the orchestrator), never by the core.
DEFAULT_CORTEX_MODEL = "cortex"


def _uuid4_turn_id() -> str:
    """Default turn-id factory; injectable so tests can pin ids."""
    return str(uuid4())


def _arm_escalation(
    caps: TurnCapabilities, working: list[Message], context: ToolLoopContext
) -> None:
    """Arm the turn's escalation slot at turn start, when one is handed in (ADR-0030).

    References to the live working list, ledger, and budget, plus the fence nonce and the
    pre-loop length, so the escalate tool writes only the brief and a later snapshot captures
    exactly this turn's appended tail. The slot is per turn by its builder's contract; a
    ``None`` slot is every escalation-less deployment, and nothing is armed.
    """
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
    """The "handle a user turn" use-case, wired only to ports.

    Event contract per turn: zero or more ``TextDelta`` / ``StatusUpdate`` / ``ToolActivity``
    (interleaved) then exactly one ``TurnCompleted``. A ``StatusUpdate`` carries ephemeral
    progress, a reasoning model's live deliberation (ADR-0020, ``state="thinking"``); a
    ``ToolActivity`` an audited dispatch (ADR-0009 addendum). Neither is accumulated into
    ``full_text`` nor recorded to memory, but the thinking detail is a rendered surface, so
    the output guardrail scrubs it as its own stream (ADR-0020 addendum); an activity's
    fields stay registry-authored by construction. The user message is persisted
    before inference starts; the assistant message is persisted only on completion. A consumer
    that closes the event stream mid-generation keeps the user message and drops the partial reply.
    """

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
        # Where each completion of this turn reports why it ended (ADR-0005 capped-reply
        # addendum). The cortex turn passed none until this arm, on the argument that a user
        # watching the reply arrive sees it stop; what they cannot see is *why* it stopped, and a
        # reply the context window cut reads exactly like one the model finished tersely.
        stops = StopLedger()
        context = ToolLoopContext(
            dispatcher=self._caps.tools,
            clock=self._clock,
            turn_id=turn_id,
            taint=taint,
            nonce=new_nonce(),
            session_id=session_id,
            # How far this turn may decode, the deployment's own (ADR-0005 capped-reply
            # addendum); ``None`` is the request this repo has always sent.
            bounds=self._caps.bounds,
            stops=stops,
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
        # The output guardrail (ADR-0015) filters what the user sees AND what is persisted:
        # the reply on record is the reply that was shown. The turn's taint ledger is passed
        # live (its URL set and tainted bit both grow as tool results arrive); the user's own
        # URLs are theirs to see again, so they are allowlisted. The reasoning status is a
        # display channel too (the overlay renders its detail), so it gets a second filter
        # under the same policy and allowlist (ADR-0020 addendum) via the thinking channel.
        channels = open_output_channels(self._caps.guardrail, taint, text)
        loop = stream_tool_loop(self._backend, model, working, context)
        # The loop's deltas become this turn's events through the shared mapping the brain
        # phase reuses after a swap (`turn_output.py`), closed deterministically so a consumer
        # that closes this generator mid-turn leaves nothing half-suspended.
        events = stream_turn_events(loop, channels, parts)
        try:
            async for event in events:
                yield event
        finally:
            await events.aclose()
        # After the channels have flushed, so the note lands under the whole reply rather than
        # ahead of a guardrail's held tail, and before the text is joined, so what is persisted is
        # what was shown.
        for event in cap_note(stops, parts):
            yield event
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT, text=full_text, at=self._clock.now(), turn_id=turn_id
        )
        await self._store.append(session_id, assistant)
        await record_exchange(self._caps, taint, session_id=session_id, query=text, reply=full_text)
        # The switcher title (ADR-0021 titles addendum): generated once, on the first turn
        # (history held exactly the just-appended user message when this turn began), and
        # persisted BEFORE completion so the overlay's turn-completion refresh already sees it,
        # which is what keeps a generated title from racing that refresh.
        if self._caps.generate_titles and len(history) == 1:
            await self._title_session(session_id, model, text, full_text, turn_id)
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)

    async def _title_session(
        self, session_id: str, model: str, user_text: str, assistant_text: str, turn_id: str
    ) -> None:
        """Generate a switcher title from the opening exchange and persist it (ADR-0021).

        Runs after the reply's own stream has closed, so the GPU lease it needs is free (a
        sequential acquire, never re-entrant), and it never touches the read/list path. A
        generation failure is absorbed and an empty title is not persisted: either leaves the
        first-message derivation in place, which is not worth failing a turn over.
        """
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
