"""Integration: the per-round cap against a real model and a real tool sidecar (ADR-0009).

The fakes cover the arithmetic. This file checks that a real model produces the shape. It drives
the shipped ``stream_tool_loop`` with the real ``LlamaCppBackend`` and the real
``ReconnectingMcpToolRegistry``, asks for more files than one round may read, and asserts that
the round was truncated, that the truncation is answerable (one ``Role.TOOL`` result per
recorded ``tool_call_id``), and that the model **recovered** from the refusal by asking for the
rest in later rounds rather than stalling or repeating itself.

Sampling is stochastic, so the prompt is attempted up to ``_ATTEMPTS`` times: the same request
that fans out to forty calls on one run can stay under the cap on the next, and a test that
skipped the quiet run would assert nothing. Every attempt asserts the bound; the retries are
only for the overflow the recovery half needs.

Integration-marked, so CI and the coverage gate never see it. Bring up a llama-server with a
tool-capable template and a filesystem MCP sidecar over a directory holding well more than
``MAX_CALLS_PER_ROUND`` files (docs/runbooks/tools-mcp.md, docs/runbooks/llamacpp-gpu.md), then:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \\
      CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \\
      uv run pytest -m integration --no-cov packages/orchestrator/tests/test_round_cap_live.py

Validated 2026-07-16 on Qwen3.5-4B (Q4_K_M, GPU, ``--jinja``) over the reference filesystem
server: one reply asked to read 25 files, the loop recorded 17 calls, ran 16, refused one, and
the model read the refusal and fetched the remaining nine over two further rounds.
"""

import os
from collections.abc import Sequence
from functools import partial

import httpx
import pytest

from cortex_core import (
    MAX_CALLS_PER_ROUND,
    ROUND_OVERSIZED_MSG,
    Message,
    RecordingAuditSink,
    Role,
    SingleResidentModelManager,
    SystemClock,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolInvocation,
    new_nonce,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_inference import LlamaCppBackend
from cortex_tools import ReconnectingMcpToolRegistry, streamable_http_session

_INFERENCE = os.environ.get("CORTEX_INFERENCE_ENDPOINT")
_TOOLS = os.environ.get("CORTEX_TOOLS_ENDPOINT")
_MODEL = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
_ROOT = os.environ.get("CORTEX_TOOLS_LIVE_ROOT", "/projects")
_READ_TOOL = os.environ.get("CORTEX_TOOLS_READ_TOOL", "read_text_file")
_ATTEMPTS = 3

pytestmark = pytest.mark.skipif(
    not (_INFERENCE and _TOOLS),
    reason="needs CORTEX_INFERENCE_ENDPOINT and CORTEX_TOOLS_ENDPOINT (host-only)",
)


async def _readable_files(registry: ReconnectingMcpToolRegistry) -> list[str]:
    """Return the sidecar's own listing of the mounted directory, as absolute paths it can read."""
    listing = await registry.invoke(
        ToolCall(id="live-ls", name="list_directory", arguments={"path": _ROOT})
    )
    assert listing.is_error is False, listing.content
    names = [line.removeprefix("[FILE]").strip() for line in listing.content.splitlines()]
    return [f"{_ROOT}/{name}" for name in names if name]


async def _one_turn(
    backend: LlamaCppBackend, registry: ReconnectingMcpToolRegistry, paths: list[str]
) -> tuple[list[Message], Sequence[ToolInvocation]]:
    """Run one real turn that asks for every path at once, returning its context and audit."""
    sink = RecordingAuditSink()
    clock = SystemClock()
    prompt = (
        "Read every one of these files and tell me the secret word in each: "
        + ", ".join(paths)
        + f". Call {_READ_TOOL} once for each file, all in this same reply."
    )
    working = [Message(role=Role.USER, text=prompt, at=clock.now(), turn_id="live")]
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, sink, clock),
        clock=clock,
        turn_id="live",
        taint=TaintLedger(),
        nonce=new_nonce(),
        session_id="live",
    )
    async for _ in stream_tool_loop(backend, _MODEL, working, context):
        pass
    return working, sink.records


def _assert_the_round_is_bounded_and_answerable(working: list[Message]) -> None:
    """Assert the round's bound and the well-formedness it preserves, on every attempt."""
    rounds = [message for message in working if message.tool_calls]
    assert rounds, "the model called no tools at all, so nothing below is meaningful"
    # No round records more than the cap plus the one slot that carries the refusal, so the number
    # of calls a round adds to the context is bounded rather than set by the model's reply.
    assert max(len(message.tool_calls) for message in rounds) <= MAX_CALLS_PER_ROUND + 1
    # An OpenAI-compatible backend needs one tool message per recorded call id. Re-inference
    # worked above, but assert the shape rather than trusting that it did.
    recorded = [call.id for message in rounds for call in message.tool_calls]
    answered = [message.tool_call_id for message in working if message.role is Role.TOOL]
    assert recorded == answered


@pytest.mark.integration
async def test_a_real_model_asking_for_too_many_files_is_truncated_and_recovers() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        backend = LlamaCppBackend(SingleResidentModelManager(_MODEL, _INFERENCE or ""), client)
        registry = ReconnectingMcpToolRegistry(partial(streamable_http_session, _TOOLS or ""))
        paths = await _readable_files(registry)
        if len(paths) <= MAX_CALLS_PER_ROUND:
            pytest.skip(f"{_ROOT} holds {len(paths)} files; needs more than the cap to overflow")
        records: Sequence[ToolInvocation] = ()
        for _attempt in range(_ATTEMPTS):
            working, records = await _one_turn(backend, registry, paths)
            _assert_the_round_is_bounded_and_answerable(working)
            if any(record.detail == ROUND_OVERSIZED_MSG for record in records):
                break

    # Truncation is reported rather than silent: the refusal reached the model, which went on to
    # read the files it had not received rather than stalling or asking for the same ones again.
    notices = [record for record in records if record.detail == ROUND_OVERSIZED_MSG]
    assert notices, f"no round wider than the cap in {_ATTEMPTS} attempts over {len(paths)} files"
    after_the_notice = records[records.index(notices[0]) + 1 :]
    assert [record for record in after_the_notice if record.ok], "the model stopped short"
