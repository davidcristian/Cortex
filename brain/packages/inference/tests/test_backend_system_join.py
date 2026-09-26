import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
from template_servers import APPLY_TEMPLATE, TemplateServer, leading_systems

from cortex_core import (
    Message,
    ModelLease,
    ModelManager,
    Role,
    SingleResidentModelManager,
    TextChunk,
)
from cortex_inference import LlamaCppBackend
from cortex_inference.request import build_payload

_ENDPOINT = "http://llama-cortex:8080"
_BRAIN_ENDPOINT = "http://model-host:8081"
_AT = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)
_LOGGER = "cortex_inference.backend"
_REPLY = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'

_Handler = (
    Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
)


def _system(text: str) -> Message:
    return Message(role=Role.SYSTEM, text=text, at=_AT, turn_id="t-1")


def _user() -> Message:
    return Message(role=Role.USER, text="hi", at=_AT, turn_id="t-1")


def _three() -> list[Message]:
    return [_system("a"), _system("b"), _system("c"), _user()]


def _backend(handler: _Handler, *, manager: ModelManager | None = None) -> LlamaCppBackend:
    leases = SingleResidentModelManager("cortex", _ENDPOINT) if manager is None else manager
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaCppBackend(leases, client)


async def _reply(backend: LlamaCppBackend, messages: list[Message], model: str = "cortex") -> str:
    stream = backend.stream(model, messages)
    return "".join([event.text async for event in stream if isinstance(event, TextChunk)])


def _wire(messages: list[Message], model: str = "cortex") -> object:
    return json.loads(json.dumps(build_payload(model, messages, (), None, None)))


async def test_a_template_that_renders_every_system_message_gets_the_request_unjoined() -> None:
    server = TemplateServer(takes_several=True, reply=_REPLY)
    assert await _reply(_backend(server), _three()) == "ok"
    assert len(server.probes) == 1
    assert server.chats == [_wire(_three())]


async def test_a_template_that_refuses_a_second_system_message_gets_them_joined() -> None:
    server = TemplateServer(takes_several=False, reply=_REPLY)
    assert await _reply(_backend(server), _three()) == "ok"
    (chat,) = server.chats
    assert chat["messages"] == [
        {"role": "system", "content": "a\nb\nc"},
        {"role": "user", "content": "hi"},
    ]


async def test_the_probe_asks_about_as_many_system_messages_as_the_request_opens_with() -> None:
    server = TemplateServer(takes_several=True, reply=_REPLY, renders_at_most=2)
    backend = _backend(server)
    two = [_system("a"), _system("b"), _user()]
    assert await _reply(backend, _three()) == "ok"
    assert await _reply(backend, two) == "ok"
    assert [len(leading_systems(probe)) for probe in server.probes] == [3, 2]
    assert server.chats[0]["messages"] == [
        {"role": "system", "content": "a\nb\nc"},
        {"role": "user", "content": "hi"},
    ]
    assert server.chats[1] == _wire(two)


async def test_one_system_message_is_sent_without_asking_the_template() -> None:
    server = TemplateServer(takes_several=False, reply=_REPLY)
    messages = [_system(" pre "), _user()]
    assert await _reply(_backend(server), messages) == "ok"
    assert server.probes == []
    assert server.chats == [_wire(messages)]


def _probe_fails_with(answer: Callable[[], httpx.Response]) -> tuple[_Handler, TemplateServer]:
    server = TemplateServer(takes_several=True, reply=_REPLY)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == APPLY_TEMPLATE:
            return answer()
        return server(request)

    return handler, server


def _unreachable() -> httpx.Response:
    msg = "no route to host"
    raise httpx.ConnectError(msg)


@pytest.mark.parametrize(
    "answer", [lambda: httpx.Response(404, text="Not Found"), _unreachable], ids=["404", "connect"]
)
async def test_a_probe_that_fails_joins_the_messages_and_warns(
    answer: Callable[[], httpx.Response], caplog: pytest.LogCaptureFixture
) -> None:
    handler, server = _probe_fails_with(answer)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert await _reply(_backend(handler), _three()) == "ok"
    assert server.chats[0]["messages"] == [
        {"role": "system", "content": "a\nb\nc"},
        {"role": "user", "content": "hi"},
    ]
    (record,) = caplog.records
    assert record.getMessage() == "system message probe failed; joining the leading system messages"
    assert (record.__dict__["endpoint"], record.__dict__["system_messages"]) == (_ENDPOINT, 3)


class _TwoServers:
    """Leases each model at its own endpoint, the way the deep tier and the cortex are served."""

    def __init__(self, endpoints: dict[str, str]) -> None:
        self._endpoints = endpoints

    @asynccontextmanager
    async def acquire(self, model: str) -> AsyncGenerator[ModelLease, None]:
        yield ModelLease(endpoint=self._endpoints[model])


async def test_the_probe_asks_the_server_the_request_was_leased_to() -> None:
    cortex = TemplateServer(takes_several=True, reply=_REPLY)
    deep = TemplateServer(takes_several=False, reply=_REPLY)
    hosts = {"llama-cortex": cortex, "model-host": deep}

    def handler(request: httpx.Request) -> httpx.Response:
        return hosts[request.url.host](request)

    manager = _TwoServers({"cortex": _ENDPOINT, "brain": _BRAIN_ENDPOINT})
    backend = _backend(handler, manager=manager)
    assert await _reply(backend, _three(), "brain") == "ok"
    assert (len(deep.probes), len(cortex.probes), cortex.chats) == (1, 0, [])
    assert deep.chats[0]["messages"] == [
        {"role": "system", "content": "a\nb\nc"},
        {"role": "user", "content": "hi"},
    ]
    assert await _reply(backend, _three(), "cortex") == "ok"
    assert cortex.chats == [_wire(_three())]


async def test_the_probe_is_logged_only_when_its_answer_for_an_endpoint_changes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = TemplateServer(takes_several=True, reply=_REPLY)
    broken = False

    def handler(request: httpx.Request) -> httpx.Response:
        if broken and request.url.path == APPLY_TEMPLATE:
            return httpx.Response(404)
        return server(request)

    backend = _backend(handler)
    two = [_system("a"), _system("b"), _user()]
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        for messages in (_three(), _three(), two):
            await _reply(backend, messages)
        server.takes_several = False
        await _reply(backend, _three())
        await _reply(backend, _three())
        broken = True
        await _reply(backend, _three())
        await _reply(backend, _three())
    lines = [
        (r.levelname, r.__dict__["system_messages"], r.__dict__.get("delivers"))
        for r in caplog.records
    ]
    assert lines == [
        ("INFO", 3, True),
        ("INFO", 2, True),
        ("INFO", 3, False),
        ("WARNING", 3, None),
    ]


async def test_cancelling_during_the_probe_frees_the_model_lease() -> None:
    manager = SingleResidentModelManager("cortex", _ENDPOINT)
    probing = asyncio.Event()

    async def handler(_request: httpx.Request) -> httpx.Response:
        probing.set()
        await asyncio.Event().wait()
        return httpx.Response(500)

    backend = _backend(handler, manager=manager)
    task = asyncio.create_task(_reply(backend, _three()))
    async with asyncio.timeout(5.0):
        await probing.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with asyncio.timeout(5.0), manager.acquire("cortex") as lease:
        assert lease.endpoint == _ENDPOINT
