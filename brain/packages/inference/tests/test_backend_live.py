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

from cortex_core import Message, ReasoningChunk, Role, SingleResidentModelManager, TextChunk
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


@pytest.mark.integration
async def test_reasoning_model_emits_reasoning_before_reply() -> None:
    """ADR-0020, host-validated 2026-07-06: the resident reasoning cortex (gemma-4-12B, thinking
    ON) streams reasoning_content, surfaced as ReasoningChunk alongside the reply TextChunks. A
    reasoning-inducing prompt (the bat-and-ball trap) reliably triggers a trace."""
    manager = SingleResidentModelManager(_MODEL, _ENDPOINT)
    messages = [
        Message(
            role=Role.USER,
            text=(
                "A bat and a ball cost $1.10 together. The bat costs $1 more than the ball. "
                "How much is the ball? Think it through, then give the answer."
            ),
            at=datetime.now(UTC),
            turn_id="live-reasoning",
        )
    ]
    # No read deadline: a reasoning model may think for a while before the reply.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=None)) as client:
        backend = LlamaCppBackend(manager, client)
        events = [event async for event in backend.stream(_MODEL, messages)]
    reasoning = [e for e in events if isinstance(e, ReasoningChunk)]
    reply = "".join(e.text for e in events if isinstance(e, TextChunk))
    assert reasoning, "reasoning_content was not surfaced as ReasoningChunk"
    assert reply.strip() != ""
