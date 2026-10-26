from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    MAX_RESULT_CHARS,
    RESULT_CUT_NOTE,
    ContextOverflowError,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    cut_result,
    result_message,
    wrap_untrusted,
)

_AT = datetime(2026, 10, 26, 4, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _AT


def test_a_result_of_exactly_the_limit_is_kept_whole() -> None:
    content = "x" * MAX_RESULT_CHARS
    assert cut_result(content) == (content, "")


def test_a_result_one_past_the_limit_is_cut_to_it_with_a_note() -> None:
    content = "x" * (MAX_RESULT_CHARS + 1)
    kept, note = cut_result(content)
    assert kept == "x" * MAX_RESULT_CHARS
    assert note == RESULT_CUT_NOTE.format(total=MAX_RESULT_CHARS + 1, shown=MAX_RESULT_CHARS)


def test_a_cut_ends_at_the_last_line_break_in_its_second_half() -> None:
    line = "worker-4 handled a request\n"
    content = line * 1000
    kept, note = cut_result(content)
    assert kept == content[: MAX_RESULT_CHARS - MAX_RESULT_CHARS % len(line) - 1]
    assert not kept.endswith("\n")
    assert f"only its first {len(kept):,} fit" in note
    assert f"{len(content):,} characters long" in note


def test_a_line_break_only_in_the_first_half_does_not_shorten_the_cut() -> None:
    content = "head\n" + "x" * (2 * MAX_RESULT_CHARS)
    kept, _ = cut_result(content)
    assert kept == content[:MAX_RESULT_CHARS]


def test_the_note_on_an_untrusted_result_follows_the_fence() -> None:
    content = "y" * (MAX_RESULT_CHARS + 50)
    result = ToolResult(call_id="c0", content=content, trust=Trust.UNTRUSTED)
    message = result_message(result, _AT, "t-1", nonce="n")
    kept, note = cut_result(content)
    assert message.text == wrap_untrusted(kept, nonce="n") + note
    assert message.text.endswith("too long to read whole.)")


def test_the_note_on_a_trusted_result_follows_the_kept_text() -> None:
    content = "z" * (MAX_RESULT_CHARS * 3)
    result = ToolResult(call_id="c0", content=content, trust=Trust.TRUSTED)
    kept, note = cut_result(content)
    assert result_message(result, _AT, "t-1", nonce="n").text == kept + note


class _ReadThenAnswer:
    """Asks for one read, then refuses a prompt past ``limit`` characters or answers."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self.tool_texts: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        tool_texts = [message.text for message in messages if message.role is Role.TOOL]
        if not tool_texts:
            yield ToolCall(id="c1", name="read", arguments={"path": "/big.log"})
            return
        self.tool_texts = tool_texts
        size = sum(len(message.text) for message in messages)
        if size > self._limit:
            msg = f"request ({size} tokens) exceeds the available context size ({self._limit})"
            raise ContextOverflowError(msg, excess=size - self._limit)
        yield TextChunk("The file is too long to read whole.")


async def test_a_result_far_past_the_context_is_cut_and_the_turn_answers() -> None:
    async def read(arguments: Mapping[str, object]) -> str:
        del arguments
        return "worker-4 handled a request\n" * 80_000

    spec = ToolSpec(name="read", description="read a file", parameters={"type": "object"})
    registry = InMemoryToolRegistry({"read": (spec, read)})
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    backend = _ReadThenAnswer(limit=16_384)
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        _FixedClock(),
        capabilities=TurnCapabilities(tools=dispatcher),
    )

    events = [event async for event in engine.handle_turn("s", "read it", turn_id="t-1")]

    assert events[-1] == TurnCompleted(
        turn_id="t-1", full_text="The file is too long to read whole."
    )
    [tool_text] = backend.tool_texts
    assert "2,160,000 characters long" in tool_text
    assert len(tool_text) < MAX_RESULT_CHARS + 400
