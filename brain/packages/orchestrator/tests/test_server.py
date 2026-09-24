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
    SPILLED_PACE_DETAIL,
    TIERS_MISSING_DETAIL,
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
    RpcPorts,
    RpcServerConfig,
    create_server,
    serve,
)
from cortex_seam import BrainServiceStub, HealthReply, HealthRequest


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
    server, port = create_server(RpcServerConfig(host="127.0.0.1", port=0), *_engine_and_store())
    await server.start()
    yield f"127.0.0.1:{port}"
    await server.stop(grace=None)


async def test_health_reports_ready_with_version(running_server: str) -> None:
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
        RpcServerConfig(host="127.0.0.1", port=0),
        *_engine_and_store(),
        RpcPorts(residency=manager),
    )
    await server.start()
    return server, f"127.0.0.1:{port}"


async def test_health_reports_the_swap_window_it_is_in() -> None:
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


async def test_health_stays_ready_and_names_a_peer_tier_that_did_not_come_back() -> None:
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"], fail={("start", "subagent-gpu"): "no such device"}
    )
    manager = SwappingModelManager(
        host,
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain", evict_models=("subagent-gpu",)),
        SystemClock(),
        AsyncioSleeper(),
    )
    server, address = await _serving(manager)
    try:
        async with manager.swap_scope("brain"):
            pass
        async with aio.insecure_channel(address) as channel:
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
        assert reply.detail == TIERS_MISSING_DETAIL.format(models="subagent-gpu")
        assert [note.text for note in reply.notes] == [reply.detail]
    finally:
        await server.stop(grace=None)


async def test_health_sends_each_serving_note_on_its_own_and_joins_them_for_detail() -> None:
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"], fail={("start", "subagent-gpu"): "no such device"}
    )
    manager = SwappingModelManager(
        host,
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain", evict_models=("subagent-gpu",)),
        SystemClock(),
        AsyncioSleeper(),
    )
    server, address = await _serving(manager)
    try:
        async with manager.swap_scope("brain"):
            manager.handoff_pace.note_pace(spilled=True)
        async with aio.insecure_channel(address) as channel:
            reply = await _health(BrainServiceStub(channel))
        tiers = TIERS_MISSING_DETAIL.format(models="subagent-gpu")
        assert reply.ready is True
        assert [note.text for note in reply.notes] == [tiers, SPILLED_PACE_DETAIL]
        assert reply.detail == f"{tiers}; {SPILLED_PACE_DETAIL}"
    finally:
        await server.stop(grace=None)


async def test_health_stays_ready_and_says_the_last_deep_task_ran_far_slower_than_measured() -> (
    None
):
    manager = _swapping_manager(ScriptedModelHost(running=["cortex"]))
    manager.handoff_pace.note_pace(spilled=True)
    server, address = await _serving(manager)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
        assert reply.detail == SPILLED_PACE_DETAIL
        assert [note.text for note in reply.notes] == [SPILLED_PACE_DETAIL]
    finally:
        await server.stop(grace=None)


async def _hold_scope(manager: SwappingModelManager) -> None:
    async with manager.swap_scope("brain"):
        pass


async def test_create_server_binds_the_configured_port() -> None:
    port = _free_loopback_port()
    server, bound = create_server(
        RpcServerConfig(host="127.0.0.1", port=port), *_engine_and_store()
    )
    assert bound == port
    await server.stop(grace=None)


async def test_serve_answers_health_and_shuts_down_on_cancel() -> None:
    port = _free_loopback_port()
    task = asyncio.create_task(
        serve(RpcServerConfig(host="127.0.0.1", port=port), *_engine_and_store())
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
    async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(channel.channel_ready(), timeout=0.5)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
async def test_serve_stops_gracefully_on_signal(signum: signal.Signals) -> None:
    port = _free_loopback_port()
    task = asyncio.create_task(
        serve(RpcServerConfig(host="127.0.0.1", port=port), *_engine_and_store())
    )
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
        os.kill(os.getpid(), signum)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()
    assert signal.getsignal(signum) in (signal.SIG_DFL, signal.default_int_handler)
    async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(channel.channel_ready(), timeout=0.5)
