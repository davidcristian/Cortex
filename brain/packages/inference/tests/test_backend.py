"""Behavior tests for LlamaCppBackend: SSE streaming, message mapping, error mapping.

The manager is the real (pure) SingleResidentModelManager; the HTTP layer is an httpx
MockTransport, so every case runs with no GPU and no network (ADR-0007 integration
boundary). Live streaming against a real llama-server is in test_backend_live.py.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from cortex_core import (
    ImagePart,
    InferenceError,
    Message,
    ModelUnavailableError,
    ReasoningChunk,
    Role,
    SingleResidentModelManager,
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
    """One streaming chat-completion chunk carrying ``delta`` (JSON-encoded, no manual escaping)."""
    return json.dumps({"choices": [{"delta": delta}]})


def _read_spec() -> ToolSpec:
    return ToolSpec(name="read", description="read a file", parameters={"type": "object"})


def _content_handler(_request: httpx.Request) -> httpx.Response:
    """A minimal one-delta response, shared by the no-[DONE] and unavailable-model tests."""
    return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"solo"}}]}'))


def _backend(handler: _Handler, *, resident: str = "cortex") -> LlamaCppBackend:
    manager = SingleResidentModelManager(resident, _ENDPOINT)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(manager, client)


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
                '{"choices":[{"delta":{"role":"assistant"}}]}',  # role-only -> no text
                '{"choices":[{"delta":{"content":"Hello"}}]}',
                '{"choices":[{"delta":{"content":", world"}}]}',
                '{"choices":[{"delta":{},"finish_reason":"stop"}]}',  # empty delta -> none
                "[DONE]",
                '{"choices":[{"delta":{"content":"past done"}}]}',  # after DONE -> ignored
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
    """A server that closes the stream without a [DONE] line still yields its content."""
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
    """A reasoning model (ADR-0020) streams reasoning_content before content; both surface as
    their own events, thinking first, and a chunk carrying both keeps that order."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                _chunk({"reasoning_content": "let me think"}),  # reasoning-only
                _chunk({"reasoning_content": " harder", "content": "the "}),  # both, order kept
                _chunk({"content": "answer"}),  # content-only
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
    # The body is what turns "500" into a diagnosis. A vision request to a llama-server started
    # without its projector is the case this exists for; without the excerpt it is
    # indistinguishable from any other failure.
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


async def test_unavailable_model_wraps_into_inference_error() -> None:
    # _content_handler never runs here: acquire('brain') raises before any request is made.
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
    # ADR-0028: a schema constrains decoding via an OpenAI json_schema response_format, so the
    # subagent runner can force a weak model's reply into the fixed envelope.
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
    # The unconstrained request is byte-for-byte the original: no response_format key at all.
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse(_chunk({"content": "ok"})))

    stream = _backend(handler).stream("cortex", _messages())
    _ = [event async for event in stream]
    body = captured["body"]
    assert isinstance(body, dict)
    assert "response_format" not in body


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
        _chunk({}),  # a terminal empty-delta chunk carries neither text nor a fragment
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


class _BlockingStream(httpx.AsyncByteStream):
    """A response body that yields one SSE line, then suspends forever (until cancelled).

    The suspension holds the consumer inside the backend's ``async with
    manager.acquire(...)`` block, so a cancel arrives while the GPU lease is held
    mid-inference: exactly the moment a user's Stop (or a client ``Cancel``) lands.
    """

    def __init__(self, first: bytes, streaming: asyncio.Event, release: asyncio.Event) -> None:
        self._first = first
        self._streaming = streaming
        self._release = release

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._first
        # Reached only when httpx pulls the body a SECOND time, which the backend does only
        # after it has surfaced the first line's TextChunk. So `streaming` being set proves
        # inference was genuinely in flight (a delta emitted) before the block below suspends.
        self._streaming.set()
        await self._release.wait()  # never set: suspend mid-stream, lease held, until cancel

    async def aclose(self) -> None:
        return None


async def test_cancelling_mid_stream_frees_the_model_lease() -> None:
    """Cancelling a turn task mid-inference must release the GPU lease so the next turn runs.

    The lease is a non-reentrant ``asyncio.Lock`` held across the whole streaming block
    (``async with manager.acquire(...)`` wrapping the HTTP stream), so a ``CancelledError``
    must propagate out through that ``async with`` and free the lock. This is the crux of a
    mid-turn Cancel / drop-to-cancel (ADR-0011): a Stop that released the lock's holder task
    but left the lock taken would wedge every later turn behind a lease no one can reclaim.
    Distrust-green: with ``acquire`` releasing outside a ``finally`` the re-acquire below
    deadlocks and the timeout reddens this test.
    """
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    streaming = asyncio.Event()  # set once the body has streamed its first line (lease held)
    release = asyncio.Event()  # never set: the body blocks here until the consumer is cancelled
    first = _sse(_chunk({"content": "partial"}))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_BlockingStream(first, streaming, release))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = LlamaCppBackend(manager, client)

    async def consume() -> None:
        async for _event in backend.stream("cortex", _messages()):
            pass  # drain: the body suspends after the first delta, holding the lease

    task = asyncio.create_task(consume())
    async with asyncio.timeout(5.0):
        await streaming.wait()  # a delta was surfaced; the task is now suspended, lease held
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The lease must be free: a fresh acquire returns at once. A leaked lock deadlocks here.
    async with asyncio.timeout(5.0):
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _ENDPOINT
    await client.aclose()


async def test_a_tool_message_with_an_image_becomes_a_content_parts_array() -> None:
    # Measured against the real cortex: a role "tool" message whose content is a parts array
    # carrying a data: URI is accepted inside a full tool-calling exchange and answered.
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
    # The images-absent request must not change at all: every text-only deployment pays nothing
    # for vision, and a regression here would be invisible without pinning the exact shape.
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


async def test_several_images_on_one_message_all_ride_the_same_parts_array() -> None:
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
