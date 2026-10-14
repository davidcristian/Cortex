from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    DENIED_MSG,
    FORGET_UNTRUSTED_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    RECALL_DENIED_MSG,
    RECALL_FORGOTTEN_MSG,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetUntrustedTool,
    GenerationBounds,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryStoreError,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
    UntrustedMemoryForget,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 14, 6, 0, 0, tzinfo=UTC)
_FORGET = ToolCall(id="f", name=FORGET_UNTRUSTED_TOOL_NAME, arguments={})


class _Clock:
    def now(self) -> datetime:
        return _AT


class _RoundsBackend:
    """Emits one scripted round of calls per step, then a plain answer."""

    def __init__(self, rounds: Sequence[Sequence[ToolCall]]) -> None:
        self._rounds = list(rounds)
        self._step = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        step, self._step = self._step, self._step + 1
        if step >= len(self._rounds):
            yield TextChunk("done")
            return
        for call in self._rounds[step]:
            yield call


async def _sent(arguments: Mapping[str, object]) -> str:
    del arguments
    return "sent"


async def _looked(arguments: Mapping[str, object]) -> ToolResult:
    del arguments
    return ToolResult(call_id="", content="seen", trust=Trust.TRUSTED)


def _send(index: int) -> ToolCall:
    return ToolCall(id=f"s{index}", name="send", arguments={"to": "a@example.com"})


async def _loop(
    rounds: Sequence[Sequence[ToolCall]],
    taint: TaintLedger,
    *,
    approve: bool = True,
    store: InMemoryMemoryStore | None = None,
) -> tuple[RecordingAuditSink, TaintLedger]:
    """Run one loop over the real forget tool and a confirmed ``send``; return the audit."""
    memory = store if store is not None else InMemoryMemoryStore()
    forget = ForgetUntrustedTool(UntrustedMemoryForget(memory, GLOBAL_MEMORY_SCOPE))
    remote = InMemoryToolRegistry(
        {
            "send": (ToolSpec("send", "send", {}, confirm_required=True), _sent),
            "look": (ToolSpec("look", "look", {}), _looked),
        }
    )
    sink = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget], remote=remote),
        sink,
        _Clock(),
        confirmer=RecordingConfirmer(answer=approve),
        policy=DispatchPolicy(record_cards={FORGET_UNTRUSTED_TOOL_NAME: forget}),
    )
    context = ToolLoopContext(
        dispatcher=dispatcher, clock=_Clock(), turn_id="t", taint=taint, nonce="n", session_id="s"
    )
    working = [Message(role=Role.USER, text="forget them", at=_AT, turn_id="t")]
    async for _ in stream_tool_loop(_RoundsBackend(rounds), "m", working, context):
        pass
    return sink, taint


def _recalled() -> TaintLedger:
    return TaintLedger(tainted=True, recalled_only=True)


async def test_a_send_after_the_forget_says_the_memories_are_gone() -> None:
    sink, taint = await _loop([[_FORGET], [_send(1)]], _recalled())
    assert [record.ok for record in sink.records] == [True, False]
    assert sink.records[-1].detail == RECALL_FORGOTTEN_MSG
    assert taint.forgotten is True


async def test_a_send_in_the_same_round_after_the_forget_says_so_too() -> None:
    sink, _ = await _loop([[_FORGET, _send(1)]], _recalled())
    assert sink.records[-1].detail == RECALL_FORGOTTEN_MSG


async def test_a_send_before_the_forget_still_names_forgetting() -> None:
    sink, _ = await _loop([[_send(1)], [_FORGET]], _recalled())
    assert sink.records[0].detail == RECALL_DENIED_MSG


async def test_a_declined_forget_leaves_the_block_naming_forgetting() -> None:
    sink, taint = await _loop([[_FORGET], [_send(1)]], _recalled(), approve=False)
    assert sink.records[-1].detail == RECALL_DENIED_MSG
    assert taint.forgotten is False


async def test_a_forget_the_store_failed_leaves_the_block_naming_forgetting() -> None:
    store = InMemoryMemoryStore()
    store.fail_with(MemoryStoreError("down"))
    sink, taint = await _loop([[_FORGET], [_send(1)]], _recalled(), store=store)
    assert sink.records[0].ok is False
    assert sink.records[-1].detail == RECALL_DENIED_MSG
    assert taint.forgotten is False


async def test_another_tool_that_succeeds_leaves_the_block_naming_forgetting() -> None:
    look = ToolCall(id="l", name="look", arguments={})
    sink, taint = await _loop([[look], [_send(1)]], _recalled())
    assert sink.records[0].ok is True
    assert sink.records[-1].detail == RECALL_DENIED_MSG
    assert taint.forgotten is False


async def test_a_turn_that_read_untrusted_content_keeps_its_own_block() -> None:
    sink, _ = await _loop([[_FORGET], [_send(1)]], TaintLedger(tainted=True))
    assert sink.records[-1].detail == DENIED_MSG


async def test_the_dispatcher_reads_the_forget_off_the_stamp() -> None:
    sink = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (ToolSpec("send", "send", {}), _sent)}), sink, _Clock()
    )
    stamp = TurnStamp(tainted=True, recalled_only=True, forgotten=True)
    result = await dispatcher.dispatch(_send(1), stamp=stamp, confirm_required=True)
    assert result.content == RECALL_FORGOTTEN_MSG
