"""The same streaming path against a real llama-server at CORTEX_INFERENCE_ENDPOINT.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually with the gpu compose up
(docs/runbooks/llamacpp-gpu.md), e.g.
`cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
uv run pytest -m integration --no-cov packages/inference`. The `--no-cov` matters, the
100% gate in addopts would otherwise fail the run.
"""

import os
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import Message, Role, SingleResidentModelManager, TextChunk
from cortex_inference import LlamaCppBackend

_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ENDPOINT = os.environ.get("CORTEX_INFERENCE_ENDPOINT", "http://127.0.0.1:8080")


@pytest.mark.integration
async def test_llama_cpp_backend_streams_from_a_live_server() -> None:
    manager = SingleResidentModelManager(_MODEL, _ENDPOINT)
    messages = [
        Message(
            role=Role.USER,
            text="Reply with the single word: pong.",
            at=datetime.now(UTC),
            turn_id="live-1",
        )
    ]
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        backend = LlamaCppBackend(manager, client)
        events = [event async for event in backend.stream(_MODEL, messages)]
    text = "".join(e.text for e in events if isinstance(e, TextChunk))
    assert text.strip() != ""
