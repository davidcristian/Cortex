"""Behavior tests for LlamaCppEmbedder: request shape, vector decode, error mapping.

The HTTP layer is an httpx MockTransport, so every case runs with no model and no network.
A live embedding server is exercised in test_embedder_live.py.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from cortex_core import EmbedderError
from cortex_embedding import LlamaCppEmbedder

_ENDPOINT = "http://llama-embed:8081"

_Handler = Callable[[httpx.Request], httpx.Response]


def _embedder(handler: _Handler, *, model: str = "embedding") -> LlamaCppEmbedder:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppEmbedder(client, _ENDPOINT, model=model)


async def test_embeds_text_and_returns_the_vector() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    embedding = await _embedder(handler, model="nomic").embed("remember this")
    assert list(embedding) == [0.1, 0.2, 0.3]
    assert captured["url"] == f"{_ENDPOINT}/v1/embeddings"
    assert captured["body"] == {"model": "nomic", "input": "remember this"}


async def test_integer_vector_elements_become_floats() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1, 0]}]})

    embedding = await _embedder(handler).embed("x")
    assert embedding == [1.0, 0.0]
    assert all(isinstance(value, float) for value in embedding)


async def test_http_status_error_wraps_into_embedder_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "loading"})

    with pytest.raises(EmbedderError, match=r"request to .* failed") as excinfo:
        await _embedder(handler).embed("x")
    assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)


async def test_transport_error_wraps_into_embedder_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        msg = "no route to host"
        raise httpx.ConnectError(msg)

    with pytest.raises(EmbedderError, match=r"request to .* failed") as excinfo:
        await _embedder(handler).embed("x")
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


async def test_missing_fields_wrap_into_embedder_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with pytest.raises(EmbedderError, match="malformed embedding response"):
        await _embedder(handler).embed("x")


async def test_non_numeric_vector_element_wraps_into_embedder_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": ["not-a-number"]}]})

    with pytest.raises(EmbedderError, match="malformed embedding response"):
        await _embedder(handler).embed("x")
