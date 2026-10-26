from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

from cortex_core import (
    NO_ROOM_NOTE,
    RESULT_CUT_NOTE,
    RESULT_ROOM_CHARS,
    ROOM_SHARED,
    SMALLER_PART,
    SMALLER_TAIL,
    TAIL_CUT_NOTE,
    GenerationBounds,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    LastLinesToolRegistry,
    Message,
    RecordingAuditSink,
    ResultRoom,
    Role,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolResult,
    ToolSpec,
    Trust,
    result_message,
    wrap_untrusted,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 26, 6, 0, tzinfo=UTC)
_LINE = "worker-4 handled request {:04d} " + "x" * 128
_FILE = "\n".join(_LINE.format(n) for n in range(1, 501)) + "\n"


class _Clock:
    def now(self) -> datetime:
        return _AT


class _RoundsBackend:
    def __init__(self, rounds: Sequence[Sequence[ToolCall]]) -> None:
        self._rounds = list(rounds)
        self.seen: list[Sequence[Message]] = []

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
        step = len(self.seen)
        self.seen.append(list(messages))
        if step >= len(self._rounds):
            yield TextChunk("done")
            return
        for call in self._rounds[step]:
            yield call


async def _read(arguments: Mapping[str, object]) -> str:
    lines = _FILE.split("\n")
    head, tail = arguments.get("head"), arguments.get("tail")
    if isinstance(head, int):
        return "\n".join(lines[:head])
    if isinstance(tail, int):
        return "\n".join(lines[-tail:])
    return _FILE


async def _note(arguments: Mapping[str, object]) -> ToolResult:
    return ToolResult(call_id="", content=str(arguments["text"]), trust=Trust.TRUSTED)


async def _server_error(arguments: Mapping[str, object]) -> ToolResult:
    del arguments
    return ToolResult(call_id="", content=_FILE, is_error=True)


_RESTING = "The files server is resting for 60 more seconds after a call overran."


async def _resting(arguments: Mapping[str, object]) -> str:
    del arguments
    raise ToolError(_RESTING)


def _read_call(index: int, **arguments: object) -> ToolCall:
    return ToolCall(id=f"c{index}", name="read", arguments={"path": f"/{index}.log", **arguments})


async def _tool_texts(rounds: Sequence[Sequence[ToolCall]], taint: TaintLedger) -> list[str]:
    registry = InMemoryToolRegistry(
        {
            "read": (ToolSpec("read", "read", {}), _read),
            "note": (ToolSpec("note", "note", {}), _note),
            "resting": (ToolSpec("resting", "resting", {}), _resting),
            "server_error": (ToolSpec("server_error", "server_error", {}), _server_error),
        }
    )
    tails = LastLinesToolRegistry(registry, tools=("read",))
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(tails, RecordingAuditSink(), _Clock()),
        clock=_Clock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
    )
    backend = _RoundsBackend(rounds)
    working = [Message(role=Role.USER, text="read it", at=_AT, turn_id="t")]
    events = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert events[-1] == "done"
    return [message.text for message in backend.seen[-1] if message.role is Role.TOOL]


def _fenced_length(text: str) -> int:
    return len(text) - len(wrap_untrusted("", nonce="n"))


async def test_the_results_of_one_round_share_the_room() -> None:
    texts = await _tool_texts([[_read_call(n) for n in range(4)]], TaintLedger())
    kept = [text.split("\n\n(This result")[0] for text in texts]
    assert sum(_fenced_length(text) for text in kept) <= RESULT_ROOM_CHARS
    assert all(_fenced_length(text) >= RESULT_ROOM_CHARS // 4 - len(_LINE) for text in kept)
    assert all(text.endswith(ROOM_SHARED + ")") for text in texts)


async def test_a_short_result_leaves_its_share_to_the_next_call_of_the_round() -> None:
    note = ToolCall(id="n0", name="note", arguments={"text": "ok"})
    texts = await _tool_texts([[note, _read_call(1)]], TaintLedger())
    assert texts[0] == "ok"
    assert _fenced_length(texts[1].split("\n\n(This result")[0]) > RESULT_ROOM_CHARS // 2
    assert texts[1].endswith(ROOM_SHARED + ")")


async def test_a_result_after_the_room_is_spent_gets_the_note_alone() -> None:
    taint = TaintLedger()
    texts = await _tool_texts([[_read_call(1)], [_read_call(2)], [_read_call(3)]], taint)
    kept = [text.split("\n\n(This result")[0] for text in texts[:2]]
    assert sum(_fenced_length(text) for text in kept) == RESULT_ROOM_CHARS
    assert texts[2] == NO_ROOM_NOTE.format(total=len(_FILE))


async def test_a_failed_call_after_the_room_is_spent_still_says_why_it_failed() -> None:
    resting = ToolCall(id="r0", name="resting", arguments={})
    texts = await _tool_texts([[_read_call(1)], [_read_call(2)], [resting]], TaintLedger())
    assert texts[2] == _RESTING


async def test_a_server_error_and_a_long_trusted_result_are_still_cut() -> None:
    error = ToolCall(id="e0", name="server_error", arguments={})
    long_note = ToolCall(id="n0", name="note", arguments={"text": "y" * RESULT_ROOM_CHARS * 2})
    for call in (error, long_note):
        [text] = await _tool_texts([[call]], TaintLedger())
        assert "only its first" in text


async def test_an_untrusted_result_with_no_room_still_taints_the_turn() -> None:
    taint = TaintLedger()
    big = ToolCall(id="n0", name="note", arguments={"text": "y" * RESULT_ROOM_CHARS})
    texts = await _tool_texts([[big], [_read_call(1)]], taint)
    assert texts[0] == "y" * RESULT_ROOM_CHARS
    assert texts[1] == NO_ROOM_NOTE.format(total=len(_FILE))
    assert taint.tainted


async def test_a_tail_read_past_the_room_keeps_the_last_lines() -> None:
    [text] = await _tool_texts([[_read_call(1, tail=100)]], TaintLedger())
    content = "\n".join(_LINE.format(n) for n in range(401, 501))
    kept = content[-RESULT_ROOM_CHARS:].split("\n", 1)[1]
    fit = kept.count("\n") + 1
    assert _LINE.format(500) in text
    assert _LINE.format(401) not in text
    assert text == wrap_untrusted(kept, nonce="n") + TAIL_CUT_NOTE.format(
        total=len(content),
        shown=len(kept),
        dropped=100 - fit,
        lines=100,
        advice=SMALLER_TAIL.format(fit=fit),
    )


async def test_a_head_read_past_the_room_keeps_the_first_lines() -> None:
    [text] = await _tool_texts([[_read_call(1, head=100)]], TaintLedger())
    assert _LINE.format(1) in text
    assert _LINE.format(100) not in text
    assert "only its first" in text
    assert text.endswith(SMALLER_PART + ")")


def test_a_tail_cut_inside_one_long_line_counts_it_as_left_out() -> None:
    content = "z" * (RESULT_ROOM_CHARS * 2)
    kept, note = ResultRoom().cut(content, keep_end=True)
    assert kept == "z" * RESULT_ROOM_CHARS
    assert note == TAIL_CUT_NOTE.format(
        total=len(content), shown=len(kept), dropped=1, lines=1, advice=SMALLER_PART
    )


def test_a_tail_cut_keeps_a_first_line_break_from_the_second_half() -> None:
    content = "z" * (RESULT_ROOM_CHARS * 2) + "\nlast"
    kept, note = ResultRoom().cut(content, keep_end=True)
    assert kept == content[-RESULT_ROOM_CHARS:]
    assert "the first 1 of its 2 lines" in note


def test_a_shared_tail_cut_says_the_room_is_shared() -> None:
    content = "line\n" * RESULT_ROOM_CHARS
    kept, note = ResultRoom().cut(content, share=2, keep_end=True)
    assert len(kept) <= RESULT_ROOM_CHARS // 2
    assert note.endswith(ROOM_SHARED + ")")


def test_the_room_shrinks_by_what_each_result_keeps() -> None:
    room = ResultRoom(100)
    assert room.cut("a" * 30) == ("a" * 30, "")
    assert room.left == 70
    kept, note = room.cut("b" * 200)
    assert kept == "b" * 70
    assert note == RESULT_CUT_NOTE.format(total=200, shown=70, advice=ROOM_SHARED)
    assert room.left == 0
    assert room.cut("") == ("", "")


def test_a_whole_note_takes_its_length_from_the_room_and_never_less_than_none() -> None:
    room = ResultRoom(100)
    assert room.whole("a" * 30) == ("a" * 30, "")
    assert room.left == 70
    assert room.whole("b" * 200) == ("b" * 200, "")
    assert room.left == 0


def test_a_room_already_spent_past_its_size_has_none_left() -> None:
    assert ResultRoom(100, spent=40).left == 60
    assert ResultRoom(100, spent=150).left == 0


def test_a_message_with_no_room_is_the_note_without_a_fence() -> None:
    result = ToolResult(call_id="c1", content="secret text", trust=Trust.UNTRUSTED)
    cut = ResultRoom(0).cut(result.content)
    message = result_message(result, _AT, "t", nonce="n", cut=cut)
    assert message.text == NO_ROOM_NOTE.format(total=len("secret text"))
    assert message.tool_call_id == "c1"


def test_an_empty_untrusted_result_is_still_fenced() -> None:
    result = ToolResult(call_id="c1", content="", trust=Trust.UNTRUSTED)
    assert result_message(result, _AT, "t", nonce="n").text == wrap_untrusted("", nonce="n")


def test_a_tail_read_with_no_room_keeps_nothing() -> None:
    content = "line\n" * 10
    assert ResultRoom(0).cut(content, keep_end=True) == (
        "",
        NO_ROOM_NOTE.format(total=len(content)),
    )
