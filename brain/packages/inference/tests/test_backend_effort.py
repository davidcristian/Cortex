import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from effort_servers import NO_EFFORT_CAPS, QWEN38_CAPS, EffortServer

from cortex_core import (
    GenerationBounds,
    Message,
    ModelLease,
    ReasoningEffort,
    Role,
    SingleResidentModelManager,
    TextChunk,
    ToolSpec,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = "http://model-host:8081"
_OTHER_ENDPOINT = "http://model-host:8082"
_AT = datetime(2026, 11, 21, 12, 0, 0, tzinfo=UTC)
_LOGGER = "cortex_inference.backend"
_REPLY = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
_MEDIUM = GenerationBounds(effort=ReasoningEffort.MEDIUM)

_SPEC = ToolSpec(
    name="read",
    description="Read a file.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}}},
)

# The bodies the adapter posted for these two requests before any request could name an effort,
# recorded from that adapter and kept as text so that no helper of today's can change them.
_OPENING = (
    b'{"model":"brain","messages":[{"role":"system","content":"be brief"},'
    b'{"role":"user","content":"hi"}],"stream":true,"tools":[{"type":"function","function":'
    b'{"name":"read","description":"Read a file.","parameters":{"type":"object","properties":'
    b'{"path":{"type":"string"}}}}}]'
)
_UNBOUNDED_BODY = _OPENING + b"}"
_BOUNDED_BODY = (
    _OPENING
    + b',"max_tokens":512,"chat_template_kwargs":{"enable_thinking":false},'
    + b'"reasoning_budget_tokens":0}'
)
_MEDIUM_BODY = _OPENING + b',"reasoning_effort":"medium"}'


def _messages() -> list[Message]:
    return [
        Message(role=Role.SYSTEM, text="be brief", at=_AT, turn_id="t-1"),
        Message(role=Role.USER, text="hi", at=_AT, turn_id="t-1"),
    ]


_UNREAD = "reasoning effort not sent because the served template does not read it"


def _backend(server: EffortServer) -> LlamaCppBackend:
    client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    manager = SingleResidentModelManager("brain", _ENDPOINT)
    return LlamaCppBackend(manager, client, send_trace_budget=True)


async def _reply(backend: LlamaCppBackend, bounds: GenerationBounds | None) -> str:
    stream = backend.stream("brain", _messages(), tools=[_SPEC], bounds=bounds)
    return "".join([event.text async for event in stream if isinstance(event, TextChunk)])


def _logged(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if "effort" in r.getMessage()]


@pytest.mark.parametrize(
    ("bounds", "body"),
    [
        (None, _UNBOUNDED_BODY),
        (GenerationBounds(), _UNBOUNDED_BODY),
        (GenerationBounds(max_tokens=512, thinking=False, trace_tokens=0), _BOUNDED_BODY),
    ],
)
async def test_a_request_naming_no_effort_is_the_request_sent_before_efforts_existed(
    bounds: GenerationBounds | None, body: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await _reply(_backend(server), bounds) == "ok"
    assert server.chats == [body]
    assert server.asked == []
    assert _logged(caplog) == []


async def test_an_effort_is_sent_as_one_added_field_where_the_template_reads_it() -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY)
    assert await _reply(_backend(server), _MEDIUM) == "ok"
    assert server.chats == [_MEDIUM_BODY]
    assert server.asked == [f"{_ENDPOINT}/props"]


async def test_the_top_level_reaches_the_qwen38_template_under_the_name_it_lists() -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY)
    assert await _reply(_backend(server), GenerationBounds(effort=ReasoningEffort.HIGH)) == "ok"
    assert json.loads(server.chats[0])["reasoning_effort"] == "xhigh"


async def test_an_effort_beside_thinking_off_is_not_sent_and_not_asked_about() -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY)
    bounds = GenerationBounds(
        max_tokens=512, thinking=False, trace_tokens=0, effort=ReasoningEffort.MEDIUM
    )
    assert await _reply(_backend(server), bounds) == "ok"
    assert server.chats == [_BOUNDED_BODY]
    assert server.asked == []


@pytest.mark.parametrize(
    ("bounds", "level", "named"),
    [
        (_MEDIUM, logging.INFO, "medium"),
        (replace(_MEDIUM, effort_written=True), logging.WARNING, "medium"),
        (GenerationBounds(effort=ReasoningEffort.LOW, effort_written=True), logging.WARNING, "low"),
    ],
)
async def test_a_template_that_reads_no_effort_gets_the_request_without_one_and_is_named_once(
    bounds: GenerationBounds, level: int, named: str, caplog: pytest.LogCaptureFixture
) -> None:
    server = EffortServer(caps=NO_EFFORT_CAPS, reply=_REPLY)
    backend = _backend(server)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await _reply(backend, bounds) == "ok"
        assert await _reply(backend, bounds) == "ok"
    assert server.chats == [_UNBOUNDED_BODY, _UNBOUNDED_BODY]
    assert len(server.asked) == 2
    assert _logged(caplog) == [(level, _UNREAD)]
    (record,) = [r for r in caplog.records if "effort" in r.getMessage()]
    assert (record.__dict__["endpoint"], record.__dict__["model"], record.__dict__["effort"]) == (
        _ENDPOINT,
        "brain",
        named,
    )


async def test_a_level_the_deployment_wrote_is_sent_and_logged_as_the_default_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await _reply(_backend(server), replace(_MEDIUM, effort_written=True)) == "ok"
    assert server.chats == [_MEDIUM_BODY]
    assert _logged(caplog) == [(logging.INFO, "reasoning effort sent")]


async def test_a_probe_that_fails_sends_no_effort_and_warns_once_with_the_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = EffortServer(caps=QWEN38_CAPS, reply=_REPLY, props_status=503)
    backend = _backend(server)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        assert await _reply(backend, _MEDIUM) == "ok"
        assert await _reply(backend, _MEDIUM) == "ok"
    assert server.chats == [_UNBOUNDED_BODY, _UNBOUNDED_BODY]
    assert _logged(caplog) == [
        (logging.WARNING, "reasoning effort probe failed; sending no effort")
    ]
    (record,) = [r for r in caplog.records if "effort" in r.getMessage()]
    assert record.__dict__["error"] == "the properties request answered HTTP 503"


async def test_the_answer_is_asked_again_on_every_request_and_a_change_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = EffortServer(caps=NO_EFFORT_CAPS, reply=_REPLY)
    backend = _backend(server)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await _reply(backend, _MEDIUM)
        server.caps = QWEN38_CAPS
        await _reply(backend, _MEDIUM)
        await _reply(backend, _MEDIUM)
        server.caps = NO_EFFORT_CAPS
        await _reply(backend, _MEDIUM)
    assert server.chats == [_UNBOUNDED_BODY, _MEDIUM_BODY, _MEDIUM_BODY, _UNBOUNDED_BODY]
    assert _logged(caplog) == [
        (logging.INFO, _UNREAD),
        (logging.INFO, "reasoning effort sent"),
        (logging.INFO, _UNREAD),
    ]
    sent = next(r for r in caplog.records if r.getMessage() == "reasoning effort sent")
    assert (
        sent.__dict__["endpoint"],
        sent.__dict__["model"],
        sent.__dict__["effort"],
        sent.__dict__["sent_as"],
    ) == (
        _ENDPOINT,
        "brain",
        "medium",
        "medium",
    )


class _TwoEndpoints:
    """A manager that leases a different endpoint for each of two models."""

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        yield ModelLease(endpoint=_ENDPOINT if model == "brain" else _OTHER_ENDPOINT)


async def test_each_endpoint_is_named_once_for_its_own_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = EffortServer(caps=NO_EFFORT_CAPS, reply=_REPLY)
    client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    backend = LlamaCppBackend(_TwoEndpoints(), client)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        for model in ("brain", "cortex", "brain", "cortex"):
            stream = backend.stream(model, _messages(), bounds=_MEDIUM)
            assert [event async for event in stream] == [TextChunk("ok")]
    named = [r.__dict__["endpoint"] for r in caplog.records if "effort" in r.getMessage()]
    assert named == [_ENDPOINT, _OTHER_ENDPOINT]
    assert server.asked == [
        f"{_ENDPOINT}/props",
        f"{_OTHER_ENDPOINT}/props",
        f"{_ENDPOINT}/props",
        f"{_OTHER_ENDPOINT}/props",
    ]
