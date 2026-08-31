"""Integration: a token cap landing inside a tool call, off a real llama-server.

The fakes prove the pairing and the policy; this proves the shape they are written for exists. A
model still writing a tool call's ``arguments`` when the cap fires leaves the adapter a fragment
of JSON, and the question the arm turns on is whether the server says it stopped at a limit before
the adapter fails to assemble that fragment. Both halves are asserted here against a real server,
and then the shipped ``PlacedAttempt`` is asked what it makes of the pair.

Integration-marked, so CI and the coverage gate never see it (AGENTS.md gate 3). The server it
wants is one shaped like a subagent tier, meaning deliberation off at the server
(``--chat-template-kwargs``, ADR-0010), because that is what makes an attempt's cap reach the tool
call rather than a trace: ``PlacedAttempt`` deliberately sends no ``thinking`` of its own.

    docker run -d --name cut-probe --gpus all --network host \\
      -v $CORTEX_MODELS_DIR:/models:ro ghcr.io/ggml-org/llama.cpp:server-cuda \\
      --model /models/$CORTEX_MODEL_FILE_CORTEX --host 0.0.0.0 --port 8080 \\
      -ngl 99 --ctx-size 16384 --parallel 1 --jinja \\
      --chat-template-kwargs '{"enable_thinking": false}'
    cd brain && CORTEX_CUT_ENDPOINT=http://127.0.0.1:8080 \\
      uv run pytest -m integration --no-cov -s \\
      packages/inference/tests/test_cut_tool_call_live.py

``--network host`` is what makes the server reachable from a host-side test on this machine, where
a compose loopback publish is not; the compose network's own address works from inside it.

Measured 2026-08-17 by the agent on the cortex artifact run in that shape (gemma-4-12B QAT q4_0,
`-ngl 99`, `-c 16384`, `--jinja`, build `b9870-2d973636e`), one run per cap, this suite as written
plus a raw-wire sweep beside it:

| stage | what came back |
| --- | --- |
| the wire, caps of 20 to 160 | `finish_reason: "length"`, 71 to 899 chars of cut `arguments` |
| the adapter | `DecodeStop(CAPPED)`, the cadence, then `MalformedToolCallError` |
| the attempt | `TRUNCATED`, the refusal naming the cap |

Before the arm the last row read `INFERENCE` quoting a JSON decode error, which the runner
re-places: a second model load, cut at the same cap, to be told the same thing.
"""

import os
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    AttemptBounds,
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    InMemoryToolRegistry,
    MalformedToolCallError,
    Message,
    RecordingAuditSink,
    Role,
    SingleResidentModelManager,
    StopReason,
    SubagentTask,
    SystemClock,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)
from cortex_core.subagent_attempt import PlacedAttempt
from cortex_inference import LlamaCppBackend

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_ENDPOINT = os.environ.get("CORTEX_CUT_ENDPOINT", "http://127.0.0.1:8080")
_MODEL = os.environ.get("CORTEX_CUT_MODEL", "cortex")
# Small enough that the cut has to land inside the long argument rather than after it, and large
# enough that the call's name and its opening brace are already on the wire.
_CAP = int(os.environ.get("CORTEX_CUT_MAX_TOKENS", "60"))
_TIMEOUT_S = 600.0
_ASK = (
    "Using the write_note tool, save a thorough 400 word explanation of why distributed systems "
    "need consensus protocols to notes/consensus.md. Put the whole explanation in the body "
    "argument."
)

_WRITE_NOTE = ToolSpec(
    name="write_note",
    description="Write a note file into the sandbox.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Where to write it."},
            "body": {"type": "string", "description": "The full text of the note."},
        },
        "required": ["path", "body"],
    },
)


async def _wrote(arguments: Mapping[str, object]) -> str:
    """Stand in for the tool the cap never lets the model reach, so the request advertises it."""
    return f"wrote {arguments.get('path')}"


def _dispatcher() -> ToolDispatcher:
    registry = InMemoryToolRegistry({_WRITE_NOTE.name: (_WRITE_NOTE, _wrote)})
    return ToolDispatcher(registry, RecordingAuditSink(), SystemClock())


def _backend(client: httpx.AsyncClient) -> LlamaCppBackend:
    return LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT), client)


async def _drain_into(stream: AsyncIterator[InferenceEvent], seen: list[InferenceEvent]) -> None:
    """Collect events until the stream raises: what arrived before it is the thing under test."""
    async for event in stream:
        seen.append(event)  # noqa: PERF401 -- a comprehension loses this list on the raise


async def test_a_real_cap_inside_a_tool_call_reports_the_stop_before_it_fails() -> None:
    """A real server reports the cap before the adapter fails on the cut tool call.

    This is the ordering the whole arm rests on, taken from a real server rather than from a
    transcript. The stop rides the final chunk and the calls are assembled only once the stream is
    over, so a consumer has already been told the completion was capped when the assembly raises.
    """
    seen: list[InferenceEvent] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        stream = _backend(client).stream(
            _MODEL,
            [Message(role=Role.USER, text=_ASK, at=datetime.now(UTC), turn_id="t-live")],
            tools=[_WRITE_NOTE],
            bounds=GenerationBounds(max_tokens=_CAP, thinking=False),
        )
        with pytest.raises(MalformedToolCallError) as excinfo:
            await _drain_into(stream, seen)

    print(f"\nfragment: {excinfo.value}")  # noqa: T201
    print(f"events:   {seen}")  # noqa: T201
    assert DecodeStop(StopReason.CAPPED) in seen
    assert not [event for event in seen if isinstance(event, ToolCall)]


async def test_the_core_reads_a_cut_tool_call_as_a_cap_and_not_as_a_dead_backend() -> None:
    """The shipped attempt reports a cut tool call as a cap rather than as a dead backend.

    This runs the shipped attempt over the shipped adapter over a real server. Without the arm it
    comes back an inference failure quoting a JSON decode error, which the runner re-places onto
    the CPU to be cut at the same cap again.
    """
    task = SubagentTask(id="t-live", instruction=_ASK, context="", at=datetime.now(UTC))
    attempt = PlacedAttempt(
        SystemClock(),
        _dispatcher(),
        constrain_output=False,
        bounds=AttemptBounds(max_tokens=_CAP, timeout_s=_TIMEOUT_S),
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        outcome = await attempt.run(task, _MODEL, _backend(client), budget=None, progress=None)

    print(f"\noutcome: {outcome.failure} text={outcome.text!r}\ndetail: {outcome.detail}")  # noqa: T201
    assert outcome.ok is False
    assert "stopped at a token limit" in outcome.detail
    assert f"{_CAP} decoded tokens per completion" in outcome.detail
    assert "malformed tool-call arguments" not in outcome.detail
