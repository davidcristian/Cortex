import asyncio
import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from drip_server import DripServer

from cortex_core import (
    GenerationBounds,
    Message,
    ReasoningEffort,
    Role,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_inference import LlamaCppBackend, effort_probe, system_probe, trace_probe
from cortex_inference.probe_bound import ProbeTimeoutError, answered_within

# Each dripped answer is 200 bytes sent 0.01 s apart, so no read waits near the bound and the whole
# answer takes at least eight times it.
_BOUND_S = 0.25
_AT = datetime(2026, 11, 21, 12, 0, 0, tzinfo=UTC)
_REPLY = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'


def _padded(answer: object) -> bytes:
    return json.dumps(answer).encode().ljust(200)


_PROPS = _padded({"chat_template_caps": {"supports_reasoning_effort": True}})
_RENDER = _padded({"prompt": "cortex system part 1 of 2 then cortex system part 2 of 2"})
_COMPLETION = _padded({"choices": [{"finish_reason": "length", "message": {"content": "."}}]})


async def _never_answered() -> httpx.Response:
    await asyncio.Event().wait()
    return httpx.Response(200)


async def _answered_at_once() -> httpx.Response:
    return httpx.Response(204)


async def test_an_exchange_answered_inside_the_bound_returns_its_response() -> None:
    assert (await answered_within(_BOUND_S, _answered_at_once())).status_code == 204


async def test_an_exchange_never_answered_raises_naming_the_bound() -> None:
    with pytest.raises(ProbeTimeoutError, match=r"no whole answer within 0\.01 s"):
        await answered_within(0.01, _never_answered())


async def test_the_effort_probe_gives_up_on_an_answer_dripped_past_its_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(effort_probe, "EFFORT_PROBE_TIMEOUT_S", _BOUND_S)
    async with (
        DripServer("/props", _PROPS).serving() as server,
        httpx.AsyncClient(trust_env=False) as client,
    ):
        with pytest.raises(effort_probe.EffortProbeError):
            await effort_probe.effort_wire_name(server.endpoint, ReasoningEffort.MEDIUM, client)
        assert 0 < server.dripped < len(_PROPS)


async def test_the_system_probe_gives_up_on_an_answer_dripped_past_its_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(system_probe, "SYSTEM_PROBE_TIMEOUT_S", _BOUND_S)
    async with (
        DripServer("/apply-template", _RENDER).serving() as server,
        httpx.AsyncClient(trust_env=False) as client,
    ):
        with pytest.raises(system_probe.SystemProbeError):
            await system_probe.delivers_system_messages(server.endpoint, "brain", 2, client)
        assert 0 < server.dripped < len(_RENDER)


async def test_the_trace_budget_probe_gives_up_on_an_answer_dripped_past_its_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(trace_probe, "TRACE_BUDGET_PROBE_TIMEOUT_S", _BOUND_S)
    async with (
        DripServer("/v1/chat/completions", _COMPLETION).serving() as server,
        httpx.AsyncClient(trust_env=False) as client,
    ):
        with pytest.raises(trace_probe.TraceProbeUnansweredError):
            await trace_probe.reads_a_trace_budget(server.endpoint, "cortex", client)
        assert 0 < server.dripped < len(_COMPLETION)


async def test_a_dripped_properties_answer_sends_the_reply_with_no_level_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(effort_probe, "EFFORT_PROBE_TIMEOUT_S", _BOUND_S)
    messages = [Message(role=Role.USER, text="hi", at=_AT, turn_id="t-1")]
    async with (
        DripServer("/props", _PROPS, reply=_REPLY).serving() as server,
        httpx.AsyncClient(trust_env=False) as client,
    ):
        backend = LlamaCppBackend(SingleResidentModelManager("brain", server.endpoint), client)
        with caplog.at_level(logging.WARNING, logger="cortex_inference.backend"):
            stream = backend.stream(
                "brain", messages, bounds=GenerationBounds(effort=ReasoningEffort.MEDIUM)
            )
            assert [event async for event in stream] == [TextChunk("ok")]
        (sent,) = server.bodies
        assert "reasoning_effort" not in json.loads(sent)
        assert 0 < server.dripped < len(_PROPS)
    assert [record.getMessage() for record in caplog.records] == [
        "reasoning effort probe failed; sending no effort"
    ]
