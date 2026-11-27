import json
from collections.abc import Callable

import httpx
import pytest

from cortex_core import EmbedderError, EmbedRole
from cortex_embedding import DEFAULT_QUERY_PREFIX, LlamaCppEmbedder

_ENDPOINT = "http://llama-embed:8081"

_Handler = Callable[[httpx.Request], httpx.Response]


def _embedder(
    handler: _Handler, *, model: str = "embedding", query_prefix: str = DEFAULT_QUERY_PREFIX
) -> LlamaCppEmbedder:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppEmbedder(client, _ENDPOINT, model=model, query_prefix=query_prefix)


def _inputs(sent: list[str]) -> _Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["input"])
        return httpx.Response(200, json={"data": [{"embedding": [0.5]}]})

    return handler


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


async def test_a_query_is_sent_after_the_cards_query_prefix() -> None:
    sent: list[str] = []
    await _embedder(_inputs(sent)).embed("when is the dentist?", role=EmbedRole.QUERY)
    assert sent == ["search_query: when is the dentist?"]


async def test_a_document_is_sent_with_no_prefix() -> None:
    sent: list[str] = []
    embedder = _embedder(_inputs(sent), query_prefix="query: ")
    await embedder.embed("the dentist is on the fourteenth", role=EmbedRole.DOCUMENT)
    await embedder.embed("the dentist moved")
    assert sent == ["the dentist is on the fourteenth", "the dentist moved"]


async def test_a_query_takes_the_prefix_it_is_given() -> None:
    sent: list[str] = []
    await _embedder(_inputs(sent), query_prefix="query: ").embed("x", role=EmbedRole.QUERY)
    await _embedder(_inputs(sent), query_prefix="").embed("y", role=EmbedRole.QUERY)
    assert sent == ["query: x", "y"]
