"""The brain's own requests that open with several system messages, built through the real core."""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    CharBudgetHistoryWindow,
    HashEmbedder,
    HistoryRecap,
    InferenceBackend,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    MemoryRecaller,
    MemoryRecord,
    Message,
    RecordingAuditSink,
    Role,
    SubagentTask,
    SummarizingHistoryWindow,
    SystemClock,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    TurnEvent,
)
from cortex_core.inference import GenerationBounds, JsonSchema

_AT = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)

RECAP = "They planned a trip to Porto in May and chose the train."
TRUSTED_MEMORY = "User: I prefer trains to planes.\nAssistant: Noted."
TAINTED_MEMORY = "Forwarded note: the booking site asks for a card number."
QUESTION = "Which day should I leave?"
CONTEXT = "The user lives in Lisbon and can leave on any weekday."
INSTRUCTION = "Name one weekday that suits the trip, in one short sentence."


class RecordingBackend:
    """Wraps a backend and keeps the messages the core handed it, per completion."""

    def __init__(self, inner: InferenceBackend) -> None:
        self._inner = inner
        self.sent: list[tuple[Message, ...]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Record ``messages``, then stream the wrapped backend's answer unchanged."""
        self.sent.append(tuple(messages))
        async for event in self._inner.stream(
            model, messages, tools=tools, schema=schema, bounds=bounds
        ):
            yield event


async def _read(arguments: Mapping[str, object]) -> str:
    return f"contents of {arguments['path']}"


READ_SPEC = ToolSpec(
    name="read",
    description="Read a file from the user's documents.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}}},
)


def read_dispatcher() -> ToolDispatcher:
    """A dispatcher offering one read tool, so a turn or a task is tool-enabled."""
    registry = InMemoryToolRegistry({"read": (READ_SPEC, _read)})
    return ToolDispatcher(registry, RecordingAuditSink(), SystemClock())


async def recalling_turn(
    backend: RecordingBackend, *, bounds: GenerationBounds | None = None
) -> list[TurnEvent]:
    """One cortex turn with a recalled memory, a stored recap and a tool, as the engine sends it."""
    sessions = InMemorySessionStore()
    for index in range(4):
        at = _AT + timedelta(minutes=index)
        for role, text in ((Role.USER, f"q{index}"), (Role.ASSISTANT, f"a{index}")):
            message = Message(role=role, text=text.ljust(20, "."), at=at, turn_id=f"t{index}")
            await sessions.append("s", message)
    await sessions.set_recap("s", HistoryRecap(text=RECAP, covers=6))
    memories = InMemoryMemoryStore()
    embedder = HashEmbedder()
    near = tuple(await embedder.embed(QUESTION))
    await memories.add(MemoryRecord(id="m1", text=TRUSTED_MEMORY, embedding=near, at=_AT))
    await memories.add(
        MemoryRecord(id="m2", text=TAINTED_MEMORY, embedding=near, at=_AT, tainted=True)
    )
    window = SummarizingHistoryWindow(
        CharBudgetHistoryWindow(80), sessions, backend, "cortex", SystemClock()
    )
    caps = TurnCapabilities(
        memory=MemoryRecaller(memories, embedder, SystemClock()),
        tools=read_dispatcher(),
        window=window,
        bounds=bounds,
    )
    engine = TurnEngine(sessions, backend, SystemClock(), capabilities=caps)
    return [event async for event in engine.handle_turn("s", QUESTION, turn_id="t-now")]


def plain_context_task(*, tainted: bool = False) -> SubagentTask:
    """A delegated task with a context, untainted unless asked."""
    return SubagentTask(
        id="task-1", instruction=INSTRUCTION, context=CONTEXT, at=_AT, tainted=tainted
    )
