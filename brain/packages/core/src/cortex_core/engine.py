"""Handle one user turn: pure orchestration over the ports, no I/O of its own.

The engine is a stateless function over the session store. Everything it knows
about a conversation is read back from ``SessionStore`` on every turn, so a process
restart or model swap between turns loses nothing (the one hard rule). Tool use adds an
in-turn loop (ADR-0009): the model may ask to run tools, the engine dispatches them, feeds
the results back, and re-infers until the model returns a final answer, all within the
turn, bounded by ``MAX_TOOL_STEPS``.
"""

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.events import TextDelta, TurnCompleted, TurnEvent
from cortex_core.memory import ScoredMemory
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.recall import MemoryRecaller
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.tools import ToolCall, ToolResult

# The logical id of the resident cortex model (ADR-0004: logical ids, never paths).
# Deployments override it via CORTEX_MODEL_CORTEX, which is read by the composition root
# (the orchestrator), never by the core.
DEFAULT_CORTEX_MODEL = "cortex"

# How many past memories to recall into a turn's context by default (ADR-0008).
DEFAULT_RECALL_K = 5

# Upper bound on inference↔tool rounds in one turn (ADR-0009): a safety net against a
# model that never stops calling tools. On exhaustion the turn ends with the text so far.
MAX_TOOL_STEPS = 8


def _uuid4_turn_id() -> str:
    """Default turn-id factory; injectable so tests can pin ids."""
    return str(uuid4())


def _render_memory_context(hits: Sequence[ScoredMemory]) -> str:
    """Render recalled memories as the body of a system context message."""
    lines = "\n".join(f"- {hit.record.text}" for hit in hits)
    return f"Relevant memories from earlier conversations:\n{lines}"


def _render_exchange(user_text: str, assistant_text: str) -> str:
    """Render one completed turn as the memory recorded at turn end (ADR-0008)."""
    return f"User: {user_text}\nAssistant: {assistant_text}"


def _call_message(text: str, calls: Sequence[ToolCall], at: datetime, turn_id: str) -> Message:
    """The assistant's tool-calling step, carrying its native ``tool_calls`` for re-inference."""
    return Message(role=Role.ASSISTANT, text=text, at=at, turn_id=turn_id, tool_calls=tuple(calls))


def _result_message(result: ToolResult, at: datetime, turn_id: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers."""
    return Message(
        role=Role.TOOL, text=result.content, at=at, turn_id=turn_id, tool_call_id=result.call_id
    )


@dataclass(frozen=True, slots=True)
class TurnCapabilities:
    """Optional collaborators that augment a turn: memory recall and tool use.

    Both default off. A bare ``TurnCapabilities()`` is the Slice 3 behavior (no recall, no
    tools). Bundled so the turn engine stays within its dependency ceiling (ruff max-args);
    future per-turn capabilities join here, not as new constructor arguments.
    """

    memory: MemoryRecaller | None = None
    tools: ToolDispatcher | None = None


class TurnEngine:
    """The "handle a user turn" use-case, wired only to ports.

    Event contract per turn: zero or more ``TextDelta`` then exactly one
    ``TurnCompleted``. The user message is persisted before inference starts; the
    assistant message is persisted only on completion. A consumer that closes the
    event stream mid-generation keeps the user message and drops the partial reply.
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
        working = list(await self._inference_messages(text, history, turn_id))
        dispatcher = self._caps.tools
        specs = await dispatcher.describe_tools() if dispatcher is not None else ()
        parts: list[str] = []
        for _step in range(MAX_TOOL_STEPS):
            calls: list[ToolCall] = []
            step_text: list[str] = []
            deltas = self._backend.stream(model, working, tools=specs)
            try:
                async for event in deltas:
                    if isinstance(event, ToolCall):
                        calls.append(event)
                    else:
                        step_text.append(event.text)
                        parts.append(event.text)
                        yield TextDelta(text=event.text)
            finally:
                # Runs on normal exhaustion, backend failure, and consumer aclose()
                # alike: an abandoned backend generator must not linger half-suspended.
                if isinstance(deltas, AsyncGenerator):
                    await deltas.aclose()
            if not calls or dispatcher is None:
                break
            working.append(_call_message("".join(step_text), calls, self._clock.now(), turn_id))
            for call in calls:
                result = await dispatcher.dispatch(call)
                working.append(_result_message(result, self._clock.now(), turn_id))
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT, text=full_text, at=self._clock.now(), turn_id=turn_id
        )
        await self._store.append(session_id, assistant)
        if self._caps.memory is not None:
            await self._caps.memory.record(_render_exchange(text, full_text))
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)

    async def _inference_messages(
        self, query: str, history: Sequence[Message], turn_id: str
    ) -> Sequence[Message]:
        """History, optionally prefixed with a system message of recalled memories.

        Memory context is derived fresh each turn and handed only to the backend. It is
        never persisted (the session store holds the real dialogue alone). Returns the
        history unchanged when memory is disabled or nothing relevant is recalled.
        """
        if self._caps.memory is None:
            return history
        hits = await self._caps.memory.recall(query, k=DEFAULT_RECALL_K)
        if not hits:
            return history
        context = Message(
            role=Role.SYSTEM,
            text=_render_memory_context(hits),
            at=self._clock.now(),
            turn_id=turn_id,
        )
        return [context, *history]
