import asyncio
import os
import signal
import socket
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio

from cortex_core import (
    RESIDENCY_DEEP,
    AsyncioSleeper,
    EchoInferenceBackend,
    InMemorySessionStore,
    ResidencyPlan,
    ScriptedModelHost,
    ScriptedServingProbe,
    ServingWatch,
    SwappingModelManager,
    SystemClock,
    TurnEngine,
)
from cortex_inference import CORTEX_DOWN
from cortex_orchestrator import (
    ORCHESTRATOR_VERSION,
    RpcPorts,
    RpcServerConfig,
    create_server,
    run_from_env,
)
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.serving_builders import build_serving_watch
from cortex_seam import BrainServiceStub, HealthReply, HealthRequest
from cortex_session import STORE_DOWN, RedisSessionStore


async def _health(ports: RpcPorts) -> HealthReply:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        store,
        ports,
    )
    await server.start()
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            health = BrainServiceStub(channel).Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            return cast("HealthReply", await health(HealthRequest()))
    finally:
        await server.stop(grace=None)


async def _watch(answer: str | None) -> ServingWatch:
    watch = ServingWatch([ScriptedServingProbe(answer=answer)])
    await watch.refresh()
    return watch


async def test_health_is_not_ready_and_says_why_while_a_part_is_not_answering() -> None:
    reply = await _health(RpcPorts(serving=await _watch(STORE_DOWN)))
    assert reply.ready is False
    assert reply.detail == STORE_DOWN
    assert list(reply.notes) == []


async def test_health_is_ready_once_every_part_answers() -> None:
    reply = await _health(RpcPorts(serving=await _watch(None)))
    assert reply.ready is True
    assert reply.detail == f"cortex-orchestrator {ORCHESTRATOR_VERSION}"


async def test_a_swap_in_progress_is_named_before_a_part_that_is_not_answering() -> None:
    manager = SwappingModelManager(
        ScriptedModelHost(running=["cortex"]),
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain"),
        SystemClock(),
        AsyncioSleeper(),
    )
    async with manager.swap_scope("brain"):
        reply = await _health(RpcPorts(residency=manager, serving=await _watch(CORTEX_DOWN)))
    assert reply.ready is False
    assert reply.detail == RESIDENCY_DEEP.detail


def _closed_port_endpoint() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def _store(server: FakeServer) -> RedisSessionStore:
    return RedisSessionStore(FakeAsyncRedis(server=server))


async def test_without_escalation_the_watch_asks_the_cortex_server_before_the_store() -> None:
    server = FakeServer()
    server.connected = False
    inference = InferenceConfig(backend="llamacpp", endpoint=_closed_port_endpoint())
    watch, close = build_serving_watch(_store(server), inference, escalation=False)
    await watch.start()
    try:
        assert watch.fault() == CORTEX_DOWN
    finally:
        await close()


async def test_with_escalation_the_watch_asks_only_the_store() -> None:
    server = FakeServer()
    inference = InferenceConfig(backend="llamacpp", endpoint="http://127.0.0.1:1")
    watch, close = build_serving_watch(_store(server), inference, escalation=True)
    await watch.start()
    try:
        assert watch.fault() is None
        server.connected = False
        await watch.refresh()
        assert watch.fault() == STORE_DOWN
    finally:
        await close()


async def test_a_backend_with_no_server_leaves_only_the_store_to_ask() -> None:
    server = FakeServer()
    server.connected = False
    watch, close = build_serving_watch(_store(server), InferenceConfig(), escalation=False)
    await watch.start()
    try:
        assert watch.fault() == STORE_DOWN
    finally:
        await close()


async def test_the_composed_brain_answers_health_from_a_reading_taken_before_it_serves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    server = FakeServer()
    server.connected = False
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            health = BrainServiceStub(channel).Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            reply = cast("HealthReply", await health(HealthRequest()))
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    assert reply.ready is False
    assert reply.detail == STORE_DOWN
