"""Server lifecycle behavior over a real loopback grpc.aio server (CI-safe, no network).

Converse behavior lives in test_converse.py (unit) and test_converse_grpc.py (wire);
this file covers Health, binding, and graceful shutdown.
"""

import asyncio
import os
import signal
import socket
from collections.abc import AsyncIterator
from typing import cast

import pytest
from grpc import aio

from cortex_core import EchoInferenceBackend, InMemorySessionStore, SystemClock, TurnEngine
from cortex_orchestrator import (
    ORCHESTRATOR_VERSION,
    EngineFactory,
    SeamServerConfig,
    create_server,
    serve,
)
from cortex_seam import BrainServiceStub, HealthReply, HealthRequest

# The generated stub's attributes are untyped wire code (gate-exempt, ADR-0002 d4);
# this helper pins the real types once so every test below stays fully typed.


async def _health(stub: BrainServiceStub) -> HealthReply:
    health = stub.Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("HealthReply", await health(HealthRequest()))


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _engine_and_store() -> tuple[EngineFactory, InMemorySessionStore]:
    store = InMemorySessionStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    return (lambda _confirmer: engine), store


@pytest.fixture
async def running_server() -> AsyncIterator[str]:
    """A BrainService bound to an ephemeral loopback port, torn down after the test."""
    server, port = create_server(SeamServerConfig(host="127.0.0.1", port=0), *_engine_and_store())
    await server.start()
    yield f"127.0.0.1:{port}"
    await server.stop(grace=None)


async def test_health_reports_ready_with_version(running_server: str) -> None:
    async with aio.insecure_channel(running_server) as channel:
        reply = await _health(BrainServiceStub(channel))
    assert reply.ready is True
    assert reply.detail == f"cortex-orchestrator {ORCHESTRATOR_VERSION}"


async def test_create_server_binds_the_configured_port() -> None:
    port = _free_loopback_port()
    server, bound = create_server(
        SeamServerConfig(host="127.0.0.1", port=port), *_engine_and_store()
    )
    assert bound == port
    await server.stop(grace=None)


async def test_serve_answers_health_and_shuts_down_on_cancel() -> None:
    port = _free_loopback_port()
    task = asyncio.create_task(
        serve(SeamServerConfig(host="127.0.0.1", port=port), *_engine_and_store())
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Graceful shutdown really stopped the listener: the port no longer accepts.
    async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(channel.channel_ready(), timeout=0.5)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
async def test_serve_stops_gracefully_on_signal(signum: signal.Signals) -> None:
    """SIGTERM (docker compose down) and SIGINT (Ctrl-C) trigger the graceful stop path."""
    port = _free_loopback_port()
    task = asyncio.create_task(
        serve(SeamServerConfig(host="127.0.0.1", port=port), *_engine_and_store())
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
        os.kill(os.getpid(), signum)
        # serve() returns cleanly (no CancelledError, no kill by default disposition).
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    # The loop handler was removed on the way out: the pre-serve disposition is back.
    assert signal.getsignal(signum) in (signal.SIG_DFL, signal.default_int_handler)
    # Graceful shutdown really stopped the listener: the port no longer accepts.
    async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(channel.channel_ready(), timeout=0.5)
