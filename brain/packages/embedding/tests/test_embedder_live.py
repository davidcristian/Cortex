import os

import httpx
import pytest
from embedder_contract import BOUND_CHECKS, Check, EmbedderUnderTest

from cortex_embedding import LlamaCppEmbedder

_DEFAULT_ENDPOINT = "http://127.0.0.1:8081"


@pytest.mark.integration
async def test_llamacpp_embedder_returns_a_stable_vector_live() -> None:
    endpoint = os.environ.get("CORTEX_EMBEDDING_ENDPOINT", _DEFAULT_ENDPOINT)
    model = os.environ.get("CORTEX_EMBEDDING_MODEL", "embedding")
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        embedder = LlamaCppEmbedder(client, endpoint, model=model)
        first = list(await embedder.embed("the sky is blue"))
        second = list(await embedder.embed("the sky is blue"))
    assert len(first) > 0
    assert first == second


@pytest.mark.integration
@pytest.mark.parametrize("check", BOUND_CHECKS, ids=lambda check: check.__name__)
async def test_the_input_bound_holds_on_the_live_server(check: Check) -> None:
    endpoint = os.environ.get("CORTEX_EMBEDDING_ENDPOINT", _DEFAULT_ENDPOINT)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        embedder = LlamaCppEmbedder(client, endpoint)
        await check(EmbedderUnderTest(embedder=embedder, break_backend=lambda: None))
