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
    assert max(len(message.tool_calls) for message in rounds) <= MAX_CALLS_PER_ROUND + 1
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

    notices = [record for record in records if record.detail == ROUND_OVERSIZED_MSG]
    assert notices, f"no round wider than the cap in {_ATTEMPTS} attempts over {len(paths)} files"
    after_the_notice = records[records.index(notices[0]) + 1 :]
    assert [record for record in after_the_notice if record.ok], "the model stopped short"
