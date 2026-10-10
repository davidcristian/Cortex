import asyncio
import gc
import logging
import os
import signal
import socket
import weakref
from collections.abc import AsyncIterator, Sequence
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    Role,
    SystemClock,
    TextChunk,
    ToolSpec,
    TurnEngine,
)
from cortex_orchestrator import (
    ERROR_CODE_BRAIN_STOPPING,
    BrainService,
    RpcServerConfig,
    serve,
)
from cortex_orchestrator.converse_stream import ConverseStream
from cortex_seam import BrainServiceStub, ClientEvent, ServerEvent, UserTurn

_STREAM_LOGGER = "cortex_orchestrator.converse_stream"


class _PausingBackend:
    """Streams one chunk, waits `pause_s`, then streams the last one."""

    def __init__(self, pause_s: float) -> None:
        self._pause_s = pause_s
        self.closed = asyncio.Event()

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        try:
            yield TextChunk("cut short")
            await asyncio.sleep(self._pause_s)
            yield TextChunk(" and done")
        finally:
            self.closed.set()


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _open_converse(stub: BrainServiceStub) -> aio.StreamStreamCall[ClientEvent, ServerEvent]:
    converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())


def _kinds(events: Sequence[ServerEvent]) -> list[str | None]:
    return [event.WhichOneof("event") for event in events]


async def _serving(
    engine: TurnEngine, store: InMemorySessionStore, drain_s: float
) -> tuple["asyncio.Task[None]", str]:
    port = _free_loopback_port()
    config = RpcServerConfig(host="127.0.0.1", port=port)
    task = asyncio.create_task(serve(config, lambda _c, _p: engine, store, drain_s=drain_s))
    address = f"127.0.0.1:{port}"
    async with aio.insecure_channel(address) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
    return task, address


async def test_a_turn_in_flight_at_shutdown_ends_as_a_stop_and_says_why() -> None:
    store = InMemorySessionStore()
    backend = _PausingBackend(3600)
    task, address = await _serving(TurnEngine(store, backend, SystemClock()), store, 0.2)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(ClientEvent(session_id="s", user_turn=UserTurn(text="an essay")))
            responses = aiter(call)
            first = await anext(responses)
            os.kill(os.getpid(), signal.SIGTERM)
            rest = [event async for event in responses]
            code = await call.code()
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    assert first.text_delta.text == "cut short"
    assert _kinds(rest)[-1] == "error"
    assert rest[-1].error.code == ERROR_CODE_BRAIN_STOPPING
    assert "turn_complete" not in _kinds(rest)
    assert code is grpc.StatusCode.OK
    assert backend.closed.is_set()
    assert [(m.role, m.text) for m in await store.history("s")] == [(Role.USER, "an essay")]


async def test_a_turn_that_ends_within_the_drain_is_stored_whole() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, _PausingBackend(0.5), SystemClock())
    task, address = await _serving(engine, store, 60.0)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(ClientEvent(session_id="s", user_turn=UserTurn(text="hello")))
            await call.done_writing()
            responses = aiter(call)
            await anext(responses)
            os.kill(os.getpid(), signal.SIGTERM)
            events = [event async for event in responses]
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    assert _kinds(events)[-1] == "turn_complete"
    assert "error" not in _kinds(events)
    assert [(m.role, m.text) for m in await store.history("s")] == [
        (Role.USER, "hello"),
        (Role.ASSISTANT, "cut short and done"),
    ]


async def test_an_open_stream_with_no_turn_ends_without_an_error() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    task, address = await _serving(engine, store, 0.2)
    try:
        async with aio.insecure_channel(address) as channel:
            call = _open_converse(BrainServiceStub(channel))
            await call.write(ClientEvent(session_id="s", user_turn=UserTurn(text="hello")))
            async for event in call:
                if event.WhichOneof("event") == "turn_complete":
                    break
            os.kill(os.getpid(), signal.SIGTERM)
            events = [event async for event in call]
            code = await call.code()
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    assert events == []
    assert code is grpc.StatusCode.OK


async def _input_held_open(first: ClientEvent) -> AsyncIterator[ClientEvent]:
    yield first
    await asyncio.sleep(3600)


async def test_shut_down_ends_the_turn_before_it_sends_the_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemorySessionStore()
    backend = _PausingBackend(3600)
    engine = TurnEngine(store, backend, SystemClock())
    stream = ConverseStream(lambda _c, _p: engine, turn_id_factory=lambda: "t-1")
    first = ClientEvent(session_id="s9", user_turn=UserTurn(text="an essay"))
    events = stream.events(_input_held_open(first))
    try:
        while (await anext(events)).WhichOneof("event") != "text_delta":
            pass
        with caplog.at_level(logging.WARNING, logger=_STREAM_LOGGER):
            await stream.shut_down()
        reason = await anext(events)
        closed_before_the_reason = backend.closed.is_set()
        rest = [event async for event in events]
    finally:
        await events.aclose()
    assert reason.error.code == ERROR_CODE_BRAIN_STOPPING
    assert closed_before_the_reason
    assert rest == []
    (record,) = caplog.records
    assert record.__dict__["session_id"] == "s9"
    assert record.__dict__["turn_id"] == "t-1"


def _live_streams() -> list[ConverseStream]:
    return [item for item in gc.get_objects() if isinstance(item, ConverseStream)]


async def _one_turn() -> AsyncIterator[ClientEvent]:
    yield ClientEvent(session_id="s", user_turn=UserTurn(text="hello"))


async def test_the_service_keeps_no_stream_that_ended() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    service = BrainService(lambda _c, _p: engine, store)
    context = cast("aio.ServicerContext[ClientEvent, ServerEvent]", None)
    known = _live_streams()
    events = service.Converse(_one_turn(), context)
    first = await anext(events)
    (stream,) = [item for item in _live_streams() if all(item is not old for old in known)]
    ended = weakref.ref(stream)
    del stream, known
    rest = [event async for event in events]
    gc.collect()
    assert _kinds([first, *rest])[-1] == "turn_complete"
    assert ended() is None
