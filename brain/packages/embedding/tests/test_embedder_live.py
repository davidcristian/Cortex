"""The Embedder contract against a real CPU llama-server at CORTEX_EMBEDDING_ENDPOINT.

Integration-marked: excluded from CI and the coverage gate (`-m "not integration"`); run
manually on a host with the embedding server up, e.g.
`cd brain && CORTEX_EMBEDDING_ENDPOINT=http://127.0.0.1:8081 \
  uv run pytest -m integration --no-cov packages/embedding`. The `--no-cov` matters, the
100% gate in the workspace addopts would otherwise fail the run.
"""

import os

import httpx
import pytest

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
    assert first == second  # identical input embeds deterministically
