from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    FORGET_CARD,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    GLOBAL_SCOPE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetUntrustedTool,
    GenerationBounds,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryRecord,
    MemoryScope,
    MemoryStoreError,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    SessionMemoryScope,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    UntrustedMemoryForget,
)
from cortex_core.loop_events import ToolStep
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 26, 2, 0, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _AT


class _ListedBackend:
    """Keeps the tool names each request offered, and emits one scripted round of calls."""

    def __init__(self, calls: Sequence[ToolCall] = ()) -> None:
        self.offered: list[list[str]] = []
        self._calls = list(calls)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, schema, bounds
        self.offered.append([spec.name for spec in tools])
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk("noted")


async def _looked(arguments: Mapping[str, object]) -> ToolResult:
    del arguments
    return ToolResult(call_id="", content="seen", trust=Trust.TRUSTED)


def _memory(memory_id: str, *, scope: str = GLOBAL_SCOPE, tainted: bool) -> MemoryRecord:
    return MemoryRecord(
        id=memory_id, text="note", embedding=(1.0,), at=_AT, scope=scope, tainted=tainted
    )


async def _turn(
    store: InMemoryMemoryStore, backend: _ListedBackend, scope: MemoryScope = GLOBAL_MEMORY_SCOPE
) -> tuple[Sequence[object], RecordingConfirmer]:
    forget = ForgetUntrustedTool(UntrustedMemoryForget(store, scope))
    remote = InMemoryToolRegistry({"look": (ToolSpec("look", "look", {}), _looked)})
    confirmer = RecordingConfirmer(answer=False)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget], remote=remote),
        RecordingAuditSink(),
        _Clock(),
        confirmer=confirmer,
        policy=DispatchPolicy(
            record_cards={FORGET_UNTRUSTED_TOOL_NAME: forget},
            offers={FORGET_UNTRUSTED_TOOL_NAME: forget},
        ),
    )
    context = ToolLoopContext(
        dispatcher=dispatcher,
        clock=_Clock(),
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="chat-a",
    )
    working = [Message(role=Role.USER, text="remember this", at=_AT, turn_id="t")]
    events = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return events, confirmer


async def test_a_chat_with_no_tainted_memory_is_not_offered_the_forget() -> None:
    store = InMemoryMemoryStore()
    await store.add(_memory("trusted", tainted=False))
    backend = _ListedBackend()
    await _turn(store, backend)
    assert backend.offered == [["look"]]


async def test_a_tainted_memory_only_another_chat_recalls_is_not_counted() -> None:
    store = InMemoryMemoryStore()
    await store.add(_memory("other chat", scope="chat-b", tainted=True))
    backend = _ListedBackend()
    await _turn(store, backend, SessionMemoryScope())
    assert backend.offered == [["look"]]


async def test_a_chat_that_can_recall_a_tainted_memory_is_offered_the_forget() -> None:
    store = InMemoryMemoryStore()
    await store.add(_memory("quoted", tainted=True))
    backend = _ListedBackend()
    await _turn(store, backend)
    assert backend.offered == [[FORGET_UNTRUSTED_TOOL_NAME, "look"]]


async def test_a_store_that_cannot_count_leaves_the_forget_offered() -> None:
    store = InMemoryMemoryStore()
    store.fail_with(MemoryStoreError("down"))
    backend = _ListedBackend()
    await _turn(store, backend)
    assert backend.offered == [[FORGET_UNTRUSTED_TOOL_NAME, "look"]]


async def test_a_withheld_forget_called_by_name_still_shows_its_card() -> None:
    store = InMemoryMemoryStore()
    call = ToolCall(id="f", name=FORGET_UNTRUSTED_TOOL_NAME, arguments={})
    backend = _ListedBackend([call])
    events, confirmer = await _turn(store, backend)
    assert backend.offered == [["look"], ["look"]]
    assert [request.reason for request in confirmer.requests] == [FORGET_CARD]
    steps = [event.tool_name for event in events if isinstance(event, ToolStep)]
    assert steps == [FORGET_UNTRUSTED_TOOL_NAME]
