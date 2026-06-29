"""Handle one user turn: pure orchestration over the ports, no I/O of its own.

The engine is a stateless function over the session store. Everything it knows
about a conversation is read back from ``SessionStore`` on every turn, so a process
restart or model swap between turns loses nothing (the one hard rule).
"""

from collections.abc import AsyncGenerator, Callable, Mapping
from uuid import uuid4

from cortex_core.conversation import Message, Role
from cortex_core.events import TextDelta, TurnCompleted, TurnEvent
from cortex_core.ports import Clock, InferenceBackend, SessionStore
from cortex_core.routing import RoutingHints, Tier, route_turn

# The logical id of the resident cortex model (ADR-0004: logical ids, never paths).
# Deployments override it via CORTEX_MODEL_CORTEX, which is read by the composition root
# (the orchestrator), never by the core.
DEFAULT_CORTEX_MODEL = "cortex"


def _uuid4_turn_id() -> str:
    """Default turn-id factory; injectable so tests can pin ids."""
    return str(uuid4())


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
        turn_id_factory: Callable[[], str] = _uuid4_turn_id,
    ) -> None:
        self._store = store
        self._backend = backend
        self._clock = clock
        self._turn_id_factory = turn_id_factory
        # Model choice is keyed off the routed tier. Only the cortex tier is servable
        # in Slice 3 (route_turn with default hints always selects it); subagent and
        # brain entries join the map when the ModelManager lands (Slices 4/7).
        self._model_by_tier: Mapping[Tier, str] = {Tier.CORTEX: cortex_model}

    async def handle_turn(self, session_id: str, text: str) -> AsyncGenerator[TurnEvent, None]:
        """Persist the user turn, stream the reply, persist it on completion."""
        model = self._model_by_tier[route_turn(RoutingHints())]
        turn_id = self._turn_id_factory()
        user = Message(role=Role.USER, text=text, at=self._clock.now(), turn_id=turn_id)
        await self._store.append(session_id, user)
        history = await self._store.history(session_id)
        deltas = self._backend.stream(model, history)
        parts: list[str] = []
        try:
            async for delta in deltas:
                parts.append(delta)
                yield TextDelta(text=delta)
        finally:
            # Runs on normal exhaustion, backend failure, and consumer aclose()
            # alike: an abandoned backend generator must not linger half-suspended.
            if isinstance(deltas, AsyncGenerator):
                await deltas.aclose()
        full_text = "".join(parts)
        assistant = Message(
            role=Role.ASSISTANT, text=full_text, at=self._clock.now(), turn_id=turn_id
        )
        await self._store.append(session_id, assistant)
        yield TurnCompleted(turn_id=turn_id, full_text=full_text)
