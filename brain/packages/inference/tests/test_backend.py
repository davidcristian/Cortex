"""Behavior tests for LlamaCppBackend: SSE streaming, message mapping, error mapping.

The manager is the real (pure) SingleResidentModelManager; the HTTP layer is an httpx
MockTransport, so every case runs with no GPU and no network (ADR-0007 integration
boundary). Live streaming against a real llama-server is in test_backend_live.py.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    InferenceError,
    Message,
    ModelUnavailableError,
    Role,
    SingleResidentModelManager,
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


def _content_handler(_request: httpx.Request) -> httpx.Response:
    """A minimal one-delta response, shared by the no-[DONE] and unavailable-model tests."""
    return httpx.Response(200, content=_sse('{"choices":[{"delta":{"content":"solo"}}]}'))


def _backend(handler: _Handler, *, resident: str = "cortex") -> LlamaCppBackend:
    manager = SingleResidentModelManager(resident, _ENDPOINT)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(manager, client)


async def _collect(backend: LlamaCppBackend, model: str = "cortex") -> list[str]:
    return [delta async for delta in backend.stream(model, _messages())]


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


async def test_http_error_status_wraps_into_inference_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    with pytest.raises(InferenceError, match=r"request failed for model 'cortex'") as excinfo:
        await _collect(_backend(handler))
    assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)


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
