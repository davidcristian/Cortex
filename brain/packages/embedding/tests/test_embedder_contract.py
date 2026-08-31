"""Both `Embedder` implementations against the same checks (`embedder_contract.py`).

The core's `HashEmbedder` and the real `LlamaCppEmbedder` over a `MockTransport` client: only the
socket is faked, so the adapter's URL building, request body, status handling, vector decode and
error wrapping are all exercised by the same four checks the fake passes. The stand-in server
answers with the digest bytes of the text it was given, as JSON **integers**, which is a shape a
server is free to send and the check on float elements is there to catch.

The live half (a real CPU llama-server) is `test_embedder_live.py`, integration-marked per
AGENTS.md gate 3.
"""

import hashlib
import json
from collections.abc import Callable

import httpx
import pytest
from embedder_contract import ALL_CHECKS, Check, EmbedderUnderTest

from cortex_core import EmbedderError, HashEmbedder
from cortex_embedding import LlamaCppEmbedder

_ENDPOINT = "http://llama-embed:8081"

# The stand-in server's vector width. Fixed for the deployment, exactly as a real model's is.
_SERVER_DIM = 8

type Build = Callable[[], tuple[EmbedderUnderTest, httpx.AsyncClient | None]]


def _server_vector(text: str) -> list[int]:
    """Return the stand-in server's answer: deterministic, one width, whole numbers."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i] for i in range(_SERVER_DIM)]


def _hash() -> tuple[EmbedderUnderTest, httpx.AsyncClient | None]:
    embedder = HashEmbedder()
    under_test = EmbedderUnderTest(
        embedder=embedder,
        break_backend=lambda: embedder.fail_with(EmbedderError("scripted embedding failure")),
    )
    return under_test, None


def _llamacpp() -> tuple[EmbedderUnderTest, httpx.AsyncClient | None]:
    """Build the real adapter over a transport a test can take away between calls."""
    world = {"broken": False}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{_ENDPOINT}/v1/embeddings", (
            "the endpoint gained a slash or lost one"
        )
        if world["broken"]:
            msg = "connection refused"
            raise httpx.ConnectError(msg)
        body: dict[str, str] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"embedding": _server_vector(body["input"])}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    under_test = EmbedderUnderTest(
        embedder=LlamaCppEmbedder(client, _ENDPOINT),
        break_backend=lambda: world.update(broken=True),
    )
    return under_test, client


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_hash, _llamacpp], ids=["hash", "llamacpp"])
async def test_the_contract_holds(check: Check, build: Build) -> None:
    under_test, client = build()
    try:
        await check(under_test)
    finally:
        if client is not None:
            await client.aclose()
