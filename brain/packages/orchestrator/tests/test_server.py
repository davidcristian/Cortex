"""Server lifecycle behavior over a real loopback grpc.aio server (CI-safe, no network).

Converse behavior lives in test_converse.py (unit) and test_converse_grpc.py (wire);
this file covers Health, binding, and graceful shutdown.

The Health cases below run against a **real** ``SwappingModelManager`` driven through a real
residency scope over the scripted host, never a stand-in reporter: a fake would answer whatever
this file handed it, which would constrain nothing about what the seam publishes.

Proof these cases can fail (each mutation applied to production code alone with the whole brain
workspace re-run, then restored, so the counts are measured rather than aimed at):
- answering ``ready=True`` unconditionally again (dropping the report branch in ``Health``)
  makes 3 tests fail and no others: ``test_health_reports_the_swap_window_it_is_in``,
  ``test_health_answers_while_a_stalled_swap_holds_the_gpu``, and
  ``test_health_tells_the_truth_about_residency_through_the_whole_wiring`` in test_swap_wiring.py;
- reading the manager's own ``_resident`` instead of the report it publishes (the wrong source:
  it calls the deep model "serving") makes 5 tests fail, the first and third of those plus three
  cases in the core's test_residency.py. It does not reach the stalled-load case, nothing being
  resident there either way;
- making the report a coroutine that takes the GPU lease fails
  ``test_health_answers_while_a_stalled_swap_holds_the_gpu`` with ``TimeoutError`` rather than
  hanging the suite, which is the point of bounding the RPC there.

The last two cases exist because an audit measured that the core's own restoring and gave-up
cases pin only which report was published: flipping ``RESIDENCY_RESTORING.serving`` or
``RESIDENCY_LOST.serving`` to ``True`` left the whole workspace passing while the seam answered
ready for the entire swap back and, after a restore gave up, for good. Both now read ``ready``
as the literal ``False`` it has to be, and each of those two mutations makes its own case here
fail (plus the core's constants case, and nothing else). Answering ready unconditionally now
makes 6 tests fail rather than 3.

Two cases are the readiness that is **true** and still has something to say. Dropping the
serving-detail branch from ``Health`` (so a healthy brain always answers its version string)
makes both fail, and each is also tied to the record behind it rather than to a string this file
arranged: dropping ``mark_missing`` in the core makes the peer one fail, and dropping the pace
note from the core's read-time composition makes the spilled-handoff one fail.
"""

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
    """Health answers not-ready during a swap, in the residency's own words, and ready again once
    the swap back has finished."""
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
    """Health answers without queueing behind the load it is reporting on (ADR-0030 decision 6).

    The swap is paused inside the host's ``start``, which is where the manager holds the GPU
    lease across the whole move, minutes at tier scale. The RPC is bounded, so a Health that
    waited on that lease fails this case on its own timeout instead of hanging the suite.
    """
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
    """The restoring window is answered at the seam, with ``ready`` asserted as the literal
    ``False``.

    The core's own case for this window compares the report to the constant that names it, which
    says nothing about what that constant claims: with ``RESIDENCY_RESTORING.serving`` flipped it
    keeps passing while the seam tells the overlay the brain is fine for the minutes a swap back
    takes. This drives the window through ``Health`` instead, paused inside the host's ``start``
    of the cortex, which is where the swap back genuinely is.
    """
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
    """After a restore gives up, Health stays not-ready for the life of the process.

    Nothing is resident, no retry is left, and the runbook's manual recovery is what clears it,
    so a ``Health`` that answered ready here would put a green dot over a GPU serving nothing for
    as long as the process lives. This is read at the seam and asserted as a literal, because the
    core's case for it can only compare the report to the constant whose readiness is in question.
    """
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
    """The reply stays ready and still names a peer tier that did not come back.

    The cortex is up and answering, so ``ready`` has to stay true or the overlay would go amber
    over a brain that is fine. What changed is that delegated work is now running on the CPU,
    which nothing else on the seam would mention, so the report's own detail wins over this
    server's version string (ADR-0030 tier-outage addendum).
    """
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
    finally:
        await server.stop(grace=None)


async def test_health_stays_ready_and_says_the_last_deep_task_ran_far_slower_than_measured() -> (
    None
):
    """A serving brain reports that the last deep task spilled, which nothing else on the seam
    would mention.

    A spilled handoff succeeds: both tiers report ready, the card reads like a fit, and only the
    throughput says otherwise (ADR-0030 spill-note addendum). The note is written where a deep
    phase writes it, through the manager's own record, so what this asserts is the seam's end of
    that path rather than a string the test arranged.
    """
    manager = _swapping_manager(ScriptedModelHost(running=["cortex"]))
    manager.handoff_pace.note_pace(spilled=True)
    server, address = await _serving(manager)
    try:
        async with aio.insecure_channel(address) as channel:
            reply = await _health(BrainServiceStub(channel))
        assert reply.ready is True
        assert reply.detail == SPILLED_PACE_DETAIL
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
