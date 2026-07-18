"""Server lifecycle behavior over a real loopback grpc.aio server (CI-safe, no network)."""

import asyncio
import os
import signal
import socket
from collections.abc import AsyncIterator
from typing import cast

import pytest
from grpc import aio

from cortex_core import (
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    AsyncioSleeper,
    EchoInferenceBackend,
    InMemorySessionStore,
    ResidencyPlan,
    ResidencyRestoreError,
    ScriptedModelHost,
    SwappingModelManager,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import (
    ORCHESTRATOR_VERSION,
    EngineFactory,
    SeamPorts,
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
    return (lambda _confirmer, _progress: engine), store


@pytest.fixture
async def running_server() -> AsyncIterator[str]:
    """A BrainService bound to an ephemeral loopback port, torn down after the test."""
    server, port = create_server(SeamServerConfig(host="127.0.0.1", port=0), *_engine_and_store())
    await server.start()
    yield f"127.0.0.1:{port}"
    await server.stop(grace=None)


async def test_health_reports_ready_with_version(running_server: str) -> None:
    """With escalation off there is no residency to read, so readiness is unconditional."""
    async with aio.insecure_channel(running_server) as channel:
        reply = await _health(BrainServiceStub(channel))
    assert reply.ready is True
    assert reply.detail == f"cortex-orchestrator {ORCHESTRATOR_VERSION}"


def _swapping_manager(host: ScriptedModelHost) -> SwappingModelManager:
    """A real ModelManager v2 over the scripted host: the reporter production wires into Health."""
    return SwappingModelManager(
        host,
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain"),
        SystemClock(),
        AsyncioSleeper(),
    )


async def _serving(manager: SwappingModelManager) -> tuple[aio.Server, str]:
    """A bound server whose Health reads this manager, exactly as the composition root wires it."""
    server, port = create_server(
        SeamServerConfig(host="127.0.0.1", port=0),
        *_engine_and_store(),
        SeamPorts(residency=manager),
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


async def test_health_reports_the_swap_window_it_is_in() -> None:
    """Not-ready between turns in the residency's own words, and green again after the swap back."""
    manager = _swapping_manager(ScriptedModelHost(running=["cortex"]))
    server, address = await _serving(manager)
    try:
        async with aio.insecure_channel(address) as channel:
            stub = BrainServiceStub(channel)
            assert (await _health(stub)).ready is True
            async with manager.swap_scope("brain"):
                deep = await _health(stub)
            restored = await _health(stub)
        assert deep.ready is False
        assert deep.detail == RESIDENCY_DEEP.detail
        assert restored.ready is True
        assert restored.detail == f"cortex-orchestrator {ORCHESTRATOR_VERSION}"
    finally:
        await server.stop(grace=None)


async def test_health_answers_while_a_stalled_swap_holds_the_gpu() -> None:
    """The probe must not queue behind the load it is reporting on (ADR-0030 decision 6)."""
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "brain")])
    manager = _swapping_manager(host)
    server, address = await _serving(manager)
    scope = asyncio.create_task(_hold_scope(manager))
    try:
        async with asyncio.timeout(10.0):
            await host.reached[("start", "brain")].wait()
        async with aio.insecure_channel(address) as channel:
            reply = await asyncio.wait_for(_health(BrainServiceStub(channel)), timeout=5.0)
        assert reply.ready is False
        assert reply.detail == RESIDENCY_LOADING.detail
    finally:
        host.release[("start", "brain")].set()
        await scope
        await server.stop(grace=None)


async def test_health_stays_not_ready_through_the_swap_back() -> None:
    """The restoring window answered at the seam, with ``ready`` read as the literal it is."""
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "cortex")])
    manager = _swapping_manager(host)
    server, address = await _serving(manager)
    scope = asyncio.create_task(_hold_scope(manager))
    try:
        async with asyncio.timeout(10.0):
            await host.reached[("start", "cortex")].wait()
        async with aio.insecure_channel(address) as channel:
            reply = await asyncio.wait_for(_health(BrainServiceStub(channel)), timeout=5.0)
        assert reply.ready is False
        assert reply.detail == RESIDENCY_RESTORING.detail
    finally:
        host.release[("start", "cortex")].set()
        await scope
        await server.stop(grace=None)


async def test_health_stays_not_ready_after_a_restore_that_gave_up() -> None:
    """The one not-ready that outlives its turn, and the loudest thing the seam can say."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _swapping_manager(host)
    server, address = await _serving(manager)
    try:
        with pytest.raises(ResidencyRestoreError):
            async with manager.swap_scope("brain"):
                pass
        async with aio.insecure_channel(address) as channel:
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is False
        assert reply.detail == RESIDENCY_LOST.detail
    finally:
        await server.stop(grace=None)


async def _hold_scope(manager: SwappingModelManager) -> None:
    async with manager.swap_scope("brain"):
        pass


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
