import json
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    MAX_CALLS_PER_ROUND,
    REPLY_CAPPED_NOTE,
    ROUND_OVERSIZED_MSG,
    DecodeStop,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    MalformedToolCallError,
    Message,
    RecordingAuditSink,
    Role,
    SingleResidentModelManager,
    StopReason,
    SystemClock,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://llama-cortex:8080"
_AT = datetime(2026, 10, 31, 5, 0, 0, tzinfo=UTC)
_KEPT = MAX_CALLS_PER_ROUND + 1
_ENGINE_LIMIT = 400
_TOOL = "set_volume"


def _line(delta: Mapping[str, object], finish: str | None = None) -> bytes:
    body = {"choices": [{"delta": delta, "finish_reason": finish, "index": 0}]}
    return f"data: {json.dumps(body)}\n\n".encode()


def _call(index: int, arguments: str = "") -> dict[str, object]:
    function = {"name": _TOOL, "arguments": arguments}
    return {"index": index, "id": f"c{index}", "function": function}


class _CallRun(httpx.AsyncByteStream):
    """An engine writing calls up to its length limit, recording how far it got and any close."""

    def __init__(self, *, limit: int = _ENGINE_LIMIT, lead: str = "") -> None:
        self.limit = limit
        self.lead = lead
        self.sent = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self.lead:
            yield _line({"content": self.lead})
        while self.sent < self.limit:
            self.sent += 1
            yield _line({"tool_calls": [_call(self.sent - 1)]})
        yield _line({}, "length")
        yield b"data: [DONE]\n\n"

    async def aclose(self) -> None:
        self.closed = True


class _Lines(httpx.AsyncByteStream):
    """A body of fixed lines, ending without ``[DONE]`` when the reader leaves early."""

    def __init__(self, *lines: bytes) -> None:
        self._lines = lines

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for line in self._lines:
            yield line


def _backend(body: httpx.AsyncByteStream) -> LlamaCppBackend:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(SingleResidentModelManager("cortex", _ENDPOINT), client)


def _messages() -> list[Message]:
    return [Message(role=Role.USER, text="hello", at=_AT, turn_id="t")]


async def _events(body: httpx.AsyncByteStream) -> list[InferenceEvent]:
    return [event async for event in _backend(body).stream("cortex", _messages())]


def _calls(events: Sequence[InferenceEvent]) -> list[ToolCall]:
    return [event for event in events if isinstance(event, ToolCall)]


async def test_a_run_of_calls_is_closed_one_past_the_cap_with_no_stop_reported() -> None:
    run = _CallRun(lead="Noted.")
    events = await _events(run)
    assert [call.id for call in _calls(events)] == [f"c{index}" for index in range(_KEPT)]
    assert events[0] == TextChunk("Noted.")
    assert run.sent == _KEPT + 1
    assert run.closed
    assert not [event for event in events if isinstance(event, DecodeStop)]


@pytest.mark.parametrize("limit", [1, MAX_CALLS_PER_ROUND, _KEPT])
async def test_a_round_the_cap_keeps_whole_is_read_to_its_end(limit: int) -> None:
    run = _CallRun(limit=limit)
    events = await _events(run)
    assert len(_calls(events)) == limit
    assert DecodeStop(StopReason.CAPPED) in events


async def test_the_call_the_cut_interrupts_is_not_read() -> None:
    lines = [_line({"tool_calls": [_call(index, "{}")]}) for index in range(_KEPT)]
    body = _Lines(*lines, _line({"tool_calls": [_call(_KEPT, '{"lev')]}))
    assert [call.arguments for call in _calls(await _events(body))] == [{}] * _KEPT


async def test_one_chunk_holding_calls_past_the_kept_ones_keeps_only_those() -> None:
    last = [_call(index, "{}") for index in range(MAX_CALLS_PER_ROUND, _KEPT + 3)]
    last[-1]["function"] = {"name": _TOOL, "arguments": '{"lev'}
    lines = [_line({"tool_calls": [_call(index, "{}")]}) for index in range(MAX_CALLS_PER_ROUND)]
    body = _Lines(*lines, _line({"tool_calls": last}))
    assert len(_calls(await _events(body))) == _KEPT


async def test_the_words_in_the_chunk_that_starts_the_cut_call_still_cross() -> None:
    lines = [_line({"tool_calls": [_call(index, "{}")]}) for index in range(_KEPT)]
    body = _Lines(*lines, _line({"content": "last", "tool_calls": [_call(_KEPT)]}))
    assert TextChunk("last") in await _events(body)


async def test_a_kept_call_with_unreadable_arguments_still_fails_as_one() -> None:
    lines = [_line({"tool_calls": [_call(index, "{}")]}) for index in range(MAX_CALLS_PER_ROUND)]
    body = _Lines(*lines, _line({"tool_calls": [_call(MAX_CALLS_PER_ROUND, '{"lev')]}))
    with pytest.raises(MalformedToolCallError):
        await _events(body)


def _turn_backend(run: _CallRun, reply: str, sent: list[bytes]) -> LlamaCppBackend:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        if len(sent) == 1:
            return httpx.Response(200, stream=run)
        return httpx.Response(200, content=_line({"content": reply}, "stop") + b"data: [DONE]\n\n")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(SingleResidentModelManager("cortex", _ENDPOINT), client)


async def test_a_turn_whose_round_was_cut_answers_the_kept_calls_and_has_no_length_note() -> None:
    ran: list[str] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        ran.append(_TOOL)
        return "done"

    audit = RecordingAuditSink()
    tools = InMemoryToolRegistry({_TOOL: (ToolSpec(_TOOL, _TOOL, {}), handler)})
    dispatcher = ToolDispatcher(tools, audit, SystemClock())
    run = _CallRun(lead="Noted. ")
    sent: list[bytes] = []
    backend = _turn_backend(run, "That is all.", sent)
    engine = TurnEngine(
        InMemorySessionStore(),
        backend,
        SystemClock(),
        capabilities=TurnCapabilities(tools=dispatcher),
    )
    shown = [
        event.text
        async for event in engine.handle_turn("s", "turn it up", turn_id="t")
        if isinstance(event, TextDelta)
    ]
    assert "".join(shown) == "Noted. That is all."
    assert REPLY_CAPPED_NOTE not in "".join(shown)
    assert run.closed
    assert run.sent == _KEPT + 1
    assert audit.records[-1].detail == ROUND_OVERSIZED_MSG
    second = json.loads(sent[1])["messages"]
    assert sum(message["role"] == "tool" for message in second) == _KEPT
