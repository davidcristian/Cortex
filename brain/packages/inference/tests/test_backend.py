import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from cortex_core import (
    DecodeCadence,
    DecodeStop,
    GenerationBounds,
    ImagePart,
    InferenceError,
    InferenceEvent,
    MalformedToolCallError,
    Message,
    ModelUnavailableError,
    ReasoningChunk,
    Role,
    SingleResidentModelManager,
    StopReason,
    TextChunk,
    ToolCall,
    ToolSpec,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://llama-cortex:8080"
_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)

_Handler = Callable[[httpx.Request], httpx.Response]


def _messages() -> list[Message]:
    return [Message(role=Role.USER, text="hello", at=_AT, turn_id="t-1")]


def _sse(*chunks: str) -> bytes:
    """Encode chunks as an OpenAI-style SSE body: one ``data:`` event per chunk."""
    return "".join(f"data: {chunk}\n\n" for chunk in chunks).encode()


def _chunk(delta: dict[str, object]) -> str:
    """One streaming chat-completion chunk holding ``delta`` (JSON-encoded, no manual escaping)."""
    return json.dumps({"choices": [{"delta": delta}]})


def _read_spec() -> ToolSpec:
    return ToolSpec(name="read", description="read a file", parameters={"type": "object"})


def _content_handler(_request: httpx.Request) -> httpx.Response:
    """A minimal one-delta response, shared by the no-[DONE] and unavailable-model tests."""
    return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"solo"}}]}'))


def _backend(
    handler: _Handler, *, resident: str = "cortex", send_trace_budget: bool = False
) -> LlamaCppBackend:
    manager = SingleResidentModelManager(resident, _ENDPOINT)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(manager, client, send_trace_budget=send_trace_budget)


async def _drain_into(stream: AsyncIterator[InferenceEvent], seen: list[InferenceEvent]) -> None:
    """Collect events until the stream raises, keeping what arrived before the raise."""
    async for event in stream:
        seen.append(event)  # noqa: PERF401 -- see above: a comprehension loses this on the raise


async def _collect(backend: LlamaCppBackend, model: str = "cortex") -> list[str]:
    stream = backend.stream(model, _messages())
    return [event.text async for event in stream if isinstance(event, TextChunk)]


async def test_streams_content_deltas_and_stops_on_done() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=_sse(
                '{"choices":[{"delta":{"role":"assistant"}}]}',
                '{"choices":[{"delta":{"content":"Hello"}}]}',
                '{"choices":[{"delta":{"content":", world"}}]}',
                '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
                "[DONE]",
                '{"choices":[{"delta":{"content":"past done"}}]}',
            ),
        )

    assert await _collect(_backend(handler)) == ["Hello", ", world"]
    assert captured["url"] == f"{_ENDPOINT}/v1/chat/completions"
    assert captured["body"] == {
        "model": "cortex",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
    }


async def test_streams_until_the_body_ends_without_done() -> None:
    assert await _collect(_backend(_content_handler)) == ["solo"]


async def test_chunk_with_no_choices_is_skipped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse('{"choices":[]}', '{"choices":[{"delta":{"content":"x"}}]}'),
        )

    assert await _collect(_backend(handler)) == ["x"]


async def test_malformed_chunk_raises_inference_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse("{not json"))

    with pytest.raises(InferenceError, match="malformed streaming chunk"):
        await _collect(_backend(handler))


async def test_non_string_content_raises_inference_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":123}}]}'))

    with pytest.raises(InferenceError, match="non-string content"):
        await _collect(_backend(handler))


async def test_streams_reasoning_before_reply_content() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                _chunk({"reasoning_content": "let me think"}),
                _chunk({"reasoning_content": " harder", "content": "the "}),
                _chunk({"content": "answer"}),
                "[DONE]",
            ),
        )

    stream = _backend(handler).stream("cortex", _messages())
    events = [event async for event in stream]
    assert events == [
        ReasoningChunk("let me think"),
        ReasoningChunk(" harder"),
        TextChunk("the "),
        TextChunk("answer"),
    ]


async def test_non_string_reasoning_content_raises_inference_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_sse('{"choices":[{"delta":{"reasoning_content":123}}]}')
        )

    with pytest.raises(InferenceError, match="non-string reasoning_content"):
        await _collect(_backend(handler))


async def test_http_error_status_quotes_the_server_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    with pytest.raises(InferenceError) as excinfo:
        await _collect(_backend(handler))
    assert str(excinfo.value) == (
        'llama-server answered 503 for model \'cortex\': {"error":"overloaded"}'
    )


async def test_an_error_body_is_quoted_only_up_to_the_excerpt_bound() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"x" * 5000)

    with pytest.raises(InferenceError) as excinfo:
        await _collect(_backend(handler))
    message = str(excinfo.value)
    assert message.startswith("llama-server answered 500 for model 'cortex': ")
    assert message.endswith("x" * 300)
    assert len(message) - len("llama-server answered 500 for model 'cortex': ") == 300


async def test_an_empty_error_body_still_names_the_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502)

    with pytest.raises(InferenceError, match=r"^llama-server answered 502 for model 'cortex'$"):
        await _collect(_backend(handler))


async def test_transport_error_wraps_into_inference_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg)

    with pytest.raises(InferenceError, match="request failed") as excinfo:
        await _collect(_backend(handler))
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


async def test_a_stalled_stream_is_named_apart_from_an_unreachable_server() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        msg = "timed out while reading the stream"
        raise httpx.ReadTimeout(msg, request=request)

    with pytest.raises(InferenceError, match=r"sent nothing for model 'cortex'") as excinfo:
        await _collect(_backend(handler))
    assert isinstance(excinfo.value.__cause__, httpx.ReadTimeout)


async def test_unavailable_model_wraps_into_inference_error() -> None:
    with pytest.raises(InferenceError, match="could not lease 'brain'") as excinfo:
        await _collect(_backend(_content_handler), model="brain")
    assert isinstance(excinfo.value.__cause__, ModelUnavailableError)


async def test_offers_tools_and_serializes_the_tool_calling_conversation() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    conversation = [
        Message(role=Role.USER, text="read it", at=_AT, turn_id="t-1"),
        Message(
            role=Role.ASSISTANT,
            text="",
            at=_AT,
            turn_id="t-1",
            tool_calls=(ToolCall(id="c1", name="read", arguments={"path": "/x"}),),
        ),
        Message(role=Role.TOOL, text="file body", at=_AT, turn_id="t-1", tool_call_id="c1"),
    ]
    stream = _backend(handler).stream("cortex", conversation, tools=[_read_spec()])
    events = [event async for event in stream]
    assert events == [TextChunk("ok")]
    assert captured["body"] == {
        "model": "cortex",
        "stream": True,
        "messages": [
            {"role": "user", "content": "read it"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "read", "arguments": '{"path": "/x"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "file body"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "read a file",
                    "parameters": {"type": "object"},
                },
            }
        ],
    }


async def test_a_schema_maps_to_a_constrained_response_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": '{"reply":"ok"}'})))

    envelope = {
        "type": "object",
        "properties": {"reply": {"type": "string"}},
        "required": ["reply"],
        "additionalProperties": False,
    }
    stream = _backend(handler, resident="subagent").stream("subagent", _messages(), schema=envelope)
    events = [event async for event in stream]
    assert events == [TextChunk('{"reply":"ok"}')]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "reply", "schema": envelope, "strict": True},
    }


async def test_no_schema_omits_the_response_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    stream = _backend(handler).stream("cortex", _messages())
    _ = [event async for event in stream]
    body = captured["body"]
    assert isinstance(body, dict)
    assert "response_format" not in body


async def test_bounds_render_as_a_token_cap_and_a_no_thinking_template_kwarg() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "an account."})))

    bounds = GenerationBounds(max_tokens=512, thinking=False)
    stream = _backend(handler).stream("cortex", _messages(), bounds=bounds)
    _ = [event async for event in stream]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["max_tokens"] == 512
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


async def test_bounds_that_ask_for_nothing_leave_the_request_as_the_server_configured_it() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    backend = _backend(handler)
    for bounds in (GenerationBounds(max_tokens=64), GenerationBounds(thinking=False)):
        _ = [event async for event in backend.stream("cortex", _messages(), bounds=bounds)]
    capped, unthinking = captured
    assert capped["max_tokens"] == 64
    assert "chat_template_kwargs" not in capped
    assert unthinking["chat_template_kwargs"] == {"enable_thinking": False}
    assert "max_tokens" not in unthinking


async def test_no_bounds_omits_every_key() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    backend = _backend(handler, send_trace_budget=True)
    _ = [event async for event in backend.stream("cortex", _messages())]
    body = captured["body"]
    assert isinstance(body, dict)
    assert "max_tokens" not in body
    assert "chat_template_kwargs" not in body
    assert "reasoning_budget_tokens" not in body


async def test_a_trace_budget_is_sent_with_the_request_where_the_engine_reads_one() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    backend = _backend(handler, send_trace_budget=True)
    for bounds in (GenerationBounds(trace_tokens=0), GenerationBounds(trace_tokens=128)):
        _ = [event async for event in backend.stream("cortex", _messages(), bounds=bounds)]
    ended, budgeted = captured
    assert ended["reasoning_budget_tokens"] == 0
    assert budgeted["reasoning_budget_tokens"] == 128


async def test_a_trace_budget_is_withheld_where_the_engine_does_not_read_one() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    bounds = GenerationBounds(max_tokens=32, thinking=False, trace_tokens=0)
    _ = [event async for event in _backend(handler).stream("cortex", _messages(), bounds=bounds)]
    body = captured["body"]
    assert isinstance(body, dict)
    assert "reasoning_budget_tokens" not in body
    assert body["max_tokens"] == 32
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


_BACKEND_LOGGER = "cortex_inference.backend"
_UNSENT_BUDGET = "trace budget not sent because its setting is off"


def _ok_handler(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))


async def _drain(backend: LlamaCppBackend, bounds: GenerationBounds | None) -> None:
    _ = [event async for event in backend.stream("cortex", _messages(), bounds=bounds)]


async def test_a_count_the_setting_withholds_is_reported_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = _backend(_ok_handler)
    bounds = GenerationBounds(trace_tokens=128)
    with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
        await asyncio.gather(_drain(backend, bounds), _drain(backend, bounds))
        await _drain(backend, bounds)
    [record] = [r for r in caplog.records if r.name == _BACKEND_LOGGER]
    assert record.levelno == logging.WARNING
    assert record.getMessage() == _UNSENT_BUDGET
    assert getattr(record, "model", None) == "cortex"
    assert getattr(record, "trace_budget", None) == 128


async def test_a_zero_with_the_thinking_switch_on_is_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
        await _drain(_backend(_ok_handler), GenerationBounds(trace_tokens=0))
    [record] = [r for r in caplog.records if r.name == _BACKEND_LOGGER]
    assert getattr(record, "trace_budget", None) == 0


async def test_nothing_is_reported_when_no_positive_count_goes_unsent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    unread = _backend(_ok_handler)
    read = _backend(_ok_handler, send_trace_budget=True)
    with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
        await _drain(unread, GenerationBounds(thinking=False, trace_tokens=0))
        await _drain(unread, GenerationBounds(max_tokens=64))
        await _drain(unread, None)
        await _drain(read, GenerationBounds(trace_tokens=128))
    assert [r for r in caplog.records if r.name == _BACKEND_LOGGER] == []


async def test_the_thinking_switch_alone_never_budgets_the_trace() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    backend = _backend(handler, send_trace_budget=True)
    bounds = GenerationBounds(max_tokens=256, thinking=False)
    _ = [event async for event in backend.stream("cortex", _messages(), bounds=bounds)]
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "reasoning_budget_tokens" not in body


async def test_reassembles_a_streamed_tool_call_and_final_text() -> None:
    content = _sse(
        _chunk({"content": "checking "}),
        _chunk(
            {
                "tool_calls": [
                    {"index": 0, "id": "c1", "function": {"name": "read", "arguments": '{"path"'}}
                ]
            }
        ),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": ':"/x"}'}}]}),
        _chunk({}),
        "[DONE]",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    stream = _backend(handler).stream("cortex", _messages(), tools=[_read_spec()])
    events = [event async for event in stream]
    assert events == [
        TextChunk("checking "),
        ToolCall(id="c1", name="read", arguments={"path": "/x"}),
    ]


async def test_tool_call_with_no_arguments_yields_an_empty_mapping() -> None:
    content = _sse(
        _chunk({"tool_calls": [{"index": 0, "id": "c2", "function": {"name": "ping"}}]}),
        "[DONE]",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    stream = _backend(handler).stream("cortex", _messages(), tools=[_read_spec()])
    events = [event async for event in stream]
    assert events == [ToolCall(id="c2", name="ping", arguments={})]


async def test_malformed_tool_call_arguments_raise_inference_error() -> None:
    content = _sse(
        _chunk(
            {
                "tool_calls": [
                    {"index": 0, "id": "c3", "function": {"name": "read", "arguments": "{not json"}}
                ]
            }
        ),
        "[DONE]",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    stream = _backend(handler).stream("cortex", _messages(), tools=[_read_spec()])
    with pytest.raises(InferenceError, match="malformed tool-call arguments"):
        [event async for event in stream]


async def test_an_unparsable_tool_call_is_the_ports_narrower_failure() -> None:
    content = _sse(
        _chunk(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "c4",
                        "function": {"name": "write", "arguments": '{"body":"In the realm of'},
                    }
                ]
            }
        ),
        '{"choices":[{"finish_reason":"length","index":0,"delta":{}}]}',
        "[DONE]",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    stream = _backend(handler).stream("cortex", _messages(), tools=[_read_spec()])
    seen: list[InferenceEvent] = []
    with pytest.raises(MalformedToolCallError):
        await _drain_into(stream, seen)
    assert seen == [DecodeStop(StopReason.CAPPED)]


class _BlockingStream(httpx.AsyncByteStream):
    """A response body that yields one SSE line, then suspends forever (until cancelled)."""

    def __init__(self, first: bytes, streaming: asyncio.Event, release: asyncio.Event) -> None:
        self._first = first
        self._streaming = streaming
        self._release = release

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._first
        self._streaming.set()
        await self._release.wait()

    async def aclose(self) -> None:
        return None


async def test_cancelling_mid_stream_frees_the_model_lease() -> None:
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    streaming = asyncio.Event()
    release = asyncio.Event()
    first = _sse(_chunk({"content": "partial"}))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_BlockingStream(first, streaming, release))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = LlamaCppBackend(manager, client)

    async def consume() -> None:
        async for _event in backend.stream("cortex", _messages()):
            pass

    task = asyncio.create_task(consume())
    async with asyncio.timeout(5.0):
        await streaming.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The lease must be free: a fresh acquire returns at once, and a leaked lock deadlocks here.
    async with asyncio.timeout(5.0):
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _ENDPOINT
    await client.aclose()


async def test_a_tool_message_with_an_image_becomes_a_content_parts_array() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))

    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=1600, height=900)
    messages = [
        Message(role=Role.USER, text="what is on my screen?", at=_AT, turn_id="t1"),
        Message(
            role=Role.TOOL,
            text="screen capture of the primary display: 1600x900 image/png",
            at=_AT,
            turn_id="t1",
            tool_call_id="c1",
            images=(picture,),
        ),
    ]
    stream = _backend(handler).stream("cortex", messages)
    assert [event async for event in stream] == [TextChunk("ok")]

    assert sent[0]["messages"] == [
        {"role": "user", "content": "what is on my screen?"},
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": [
                {
                    "type": "text",
                    "text": "screen capture of the primary display: 1600x900 image/png",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,iVBORw=="},
                },
            ],
        },
    ]


async def test_a_tool_message_without_images_is_byte_identical_to_before() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))

    messages = [
        Message(role=Role.TOOL, text="volume is at 30%", at=_AT, turn_id="t1", tool_call_id="c1"),
    ]
    stream = _backend(handler).stream("cortex", messages)
    assert [event async for event in stream] == [TextChunk("ok")]

    assert sent[0]["messages"] == [
        {"role": "tool", "tool_call_id": "c1", "content": "volume is at 30%"}
    ]


async def test_a_user_message_with_an_attached_image_becomes_a_content_parts_array() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))

    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=640, height=480)
    messages = [
        Message(role=Role.USER, text="what is this?", at=_AT, turn_id="t1", images=(picture,))
    ]
    stream = _backend(handler).stream("cortex", messages)
    assert [event async for event in stream] == [TextChunk("ok")]

    assert sent[0]["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is this?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw=="}},
            ],
        }
    ]


async def test_several_images_on_one_message_all_go_in_the_same_parts_array() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"ok"}}]}'))

    parts = tuple(
        ImagePart(data=b"\x89PNG" + bytes([n]), mime_type="image/png", width=8, height=8)
        for n in range(2)
    )
    messages = [
        Message(role=Role.TOOL, text="two", at=_AT, turn_id="t1", tool_call_id="c1", images=parts)
    ]
    stream = _backend(handler).stream("cortex", messages)
    assert [event async for event in stream] == [TextChunk("ok")]

    sent_messages = cast("list[dict[str, object]]", sent[0]["messages"])
    content = cast("list[dict[str, object]]", sent_messages[0]["content"])
    assert [part["type"] for part in content] == ["text", "image_url", "image_url"]


def _timings(**fields: object) -> str:
    """One chunk holding a llama.cpp ``timings`` object, in the shape a live run emits."""
    body = {"cache_n": 0, "prompt_n": 25, "predicted_ms": 1297.264, **fields}
    return json.dumps(
        {"choices": [{"finish_reason": "stop", "index": 0, "delta": {}}], "timings": body}
    )


async def test_the_servers_timings_close_the_stream_as_one_cadence() -> None:
    body = _sse(
        '{"choices":[{"delta":{"content":"hi"}}]}',
        _timings(predicted_per_second=61.66824948507013, predicted_n=80),
        "[DONE]",
    )
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [
        TextChunk("hi"),
        DecodeStop(StopReason.FINISHED),
        DecodeCadence(tokens_per_second=61.66824948507013, tokens=80),
    ]


# A chunk holding both is the one case where the order is the adapter's own, so it is checked
# here rather than in the shared contract: on this build the ``timings`` object arrives on a
# content-less final chunk, which satisfies the contract's ordering check either way.
async def test_content_precedes_the_cadence_when_one_chunk_has_both() -> None:
    chunk = json.dumps(
        {
            "choices": [{"finish_reason": "stop", "index": 0, "delta": {"content": "last"}}],
            "timings": {"predicted_per_second": 30.5, "predicted_n": 64},
        }
    )
    stream = _backend(lambda _r: httpx.Response(200, content=_sse(chunk, "[DONE]"))).stream(
        "cortex", _messages()
    )
    assert [event async for event in stream] == [
        TextChunk("last"),
        DecodeStop(StopReason.FINISHED),
        DecodeCadence(tokens_per_second=30.5, tokens=64),
    ]


async def test_a_choiceless_final_chunk_still_yields_its_cadence() -> None:
    chunk = json.dumps(
        {"choices": [], "timings": {"predicted_per_second": 12.0, "predicted_n": 40}}
    )
    stream = _backend(lambda _r: httpx.Response(200, content=_sse(chunk, "[DONE]"))).stream(
        "cortex", _messages()
    )
    assert [event async for event in stream] == [DecodeCadence(tokens_per_second=12.0, tokens=40)]


@pytest.mark.parametrize(
    "timings",
    [
        pytest.param("null", id="not-an-object"),
        pytest.param('{"predicted_n":80}', id="no-rate"),
        pytest.param('{"predicted_per_second":61.6}', id="no-token-count"),
        pytest.param('{"predicted_per_second":"fast","predicted_n":80}', id="rate-not-a-number"),
        pytest.param('{"predicted_per_second":true,"predicted_n":80}', id="rate-is-a-bool"),
        pytest.param('{"predicted_per_second":61.6,"predicted_n":true}', id="tokens-are-a-bool"),
        pytest.param('{"predicted_per_second":-1.0,"predicted_n":80}', id="negative-rate"),
        pytest.param('{"predicted_per_second":61.6,"predicted_n":-3}', id="negative-tokens"),
    ],
)
async def test_an_unusable_timings_object_yields_no_cadence_and_keeps_the_reply(
    timings: str,
) -> None:
    body = _sse(
        '{"choices":[{"delta":{"content":"hi"}}]}',
        f'{{"choices":[{{"delta":{{}}}}],"timings":{timings}}}',
        "[DONE]",
    )
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [TextChunk("hi")]


# llama.cpp reports floats; a build answering ints, or a float token count, is not a violation.
async def test_a_whole_number_rate_and_count_are_taken_as_written() -> None:
    timings = json.dumps({"predicted_per_second": 30, "predicted_n": 64.0})
    body = _sse(f'{{"choices":[{{"delta":{{}}}}],"timings":{timings}}}', "[DONE]")
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [DecodeCadence(tokens_per_second=30.0, tokens=64)]


@pytest.mark.parametrize(
    ("wire", "reason"),
    [
        pytest.param("stop", StopReason.FINISHED, id="stop"),
        pytest.param("length", StopReason.CAPPED, id="length"),
        pytest.param("tool_calls", StopReason.CALLED, id="tool-calls"),
        pytest.param("content_filter", StopReason.UNKNOWN, id="a-word-this-core-has-not-learned"),
    ],
)
async def test_the_servers_finish_reason_crosses_the_port_as_a_closed_set(
    wire: str, reason: StopReason
) -> None:
    body = _sse(
        '{"choices":[{"delta":{"content":"hi"}}]}',
        f'{{"choices":[{{"finish_reason":"{wire}","index":0,"delta":{{}}}}]}}',
        "[DONE]",
    )
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [TextChunk("hi"), DecodeStop(reason)]


async def test_a_finish_reason_that_is_not_even_a_string_still_reports_a_stop() -> None:
    body = _sse('{"choices":[{"finish_reason":7,"index":0,"delta":{"content":"hi"}}]}', "[DONE]")
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [
        TextChunk("hi"),
        DecodeStop(StopReason.UNKNOWN),
    ]


# llama-server puts ``finish_reason: null`` on every chunk but the final one, so a stream of
# four chunks must yield exactly one stop and not four.
async def test_the_chunks_before_the_last_have_no_stop() -> None:
    body = _sse(
        '{"choices":[{"finish_reason":null,"delta":{"content":"a"}}]}',
        '{"choices":[{"finish_reason":null,"delta":{"content":"b"}}]}',
        '{"choices":[{"delta":{"content":"c"}}]}',
        '{"choices":[{"finish_reason":"stop","index":0,"delta":{}}]}',
        "[DONE]",
    )
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [
        TextChunk("a"),
        TextChunk("b"),
        TextChunk("c"),
        DecodeStop(StopReason.FINISHED),
    ]


async def test_a_stop_and_a_cadence_on_one_chunk_arrive_stop_first() -> None:
    chunk = json.dumps(
        {
            "choices": [{"finish_reason": "length", "index": 0, "delta": {"content": "cut"}}],
            "timings": {"predicted_per_second": 1.81, "predicted_n": 8},
        }
    )
    stream = _backend(lambda _r: httpx.Response(200, content=_sse(chunk, "[DONE]"))).stream(
        "cortex", _messages()
    )
    assert [event async for event in stream] == [
        TextChunk("cut"),
        DecodeStop(StopReason.CAPPED),
        DecodeCadence(tokens_per_second=1.81, tokens=8),
    ]


async def test_the_stop_precedes_the_tool_calls_it_ends_the_completion_for() -> None:
    body = _sse(
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        '"function":{"name":"clock_now","arguments":"{}"}}]}}]}',
        '{"choices":[{"finish_reason":"tool_calls","index":0,"delta":{}}]}',
        "[DONE]",
    )
    stream = _backend(lambda _r: httpx.Response(200, content=body)).stream("cortex", _messages())
    assert [event async for event in stream] == [
        DecodeStop(StopReason.CALLED),
        ToolCall(id="c1", name="clock_now", arguments={}),
    ]
