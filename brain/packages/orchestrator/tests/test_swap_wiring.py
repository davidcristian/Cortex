import asyncio
import logging
import os
import signal
import socket
from collections.abc import Callable, Iterable
from dataclasses import replace
from http import HTTPStatus
from typing import cast

import httpx
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from grpc import aio
from redis.asyncio import Redis

from cortex_core import (
    ESCALATE_TOOL_NAME,
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    TIERS_MISSING_DETAIL,
    AsyncioSleeper,
    Clock,
    ControlBounds,
    InMemoryBodyGateway,
    ModelHostState,
    PlacementRequest,
    PlacementTarget,
    PlainFormatter,
    ScriptedModelHost,
    Sleeper,
    SubagentPlacer,
    SwappingModelManager,
    SystemClock,
    VramBudgetPlacer,
)
from cortex_model_manager import HttpModelHost, ModelHostConfig
from cortex_orchestrator import (
    BrainRuntimeConfig,
    ControlDeadlineError,
    InferenceConfig,
    SwapConfig,
    SwapRuntime,
    build_builtin_tools,
    build_swap_runtime,
    check_control_deadline,
    recover_boot_residency,
    run_from_env,
    swap_builders,
    swap_closer,
    wiring,
)
from cortex_seam import (
    BrainServiceStub,
    ClientEvent,
    HealthReply,
    HealthRequest,
    ServerEvent,
    UserTurn,
)
from cortex_session import RedisHandoffStore, RedisSessionStore


def _stuck_host(*, running: Iterable[str]) -> ScriptedModelHost:
    """The composition root's own scripted host, with every tier it seeds stuck ``LOADING``."""
    seeded = list(running)
    return ScriptedModelHost(
        running=seeded, status_override=dict.fromkeys(seeded, ModelHostState.LOADING)
    )


def _free_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _enabled(**overrides: object) -> SwapConfig:
    fields: dict[str, object] = {
        "escalation": True,
        "modelhost_backend": "scripted",
        "brain_endpoint": "http://llama-brain:8081",
    }
    return SwapConfig(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _fake_handoff_store(url: str) -> RedisHandoffStore:
    del url
    return RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))


class _RecordingHandoffStore(RedisHandoffStore):
    """A handoff store that says when it was released, and can refuse to be released at all."""

    def __init__(self, released: list[str], *, refuse: bool = False) -> None:
        super().__init__(FakeAsyncRedis(server=FakeServer()))
        self._released = released
        self._refuse = refuse

    async def aclose(self) -> None:
        self._released.append("handoff store")
        await super().aclose()
        if self._refuse:
            msg = "the store's connection could not be released"
            raise OSError(msg)


def _supervisor_runtime(
    monkeypatch: pytest.MonkeyPatch,
    released: list[str],
    *,
    refuse_store_close: bool = False,
    bounds: ControlBounds | None = None,
) -> tuple[SwapRuntime, httpx.AsyncClient, list[str]]:
    """The real-backend runtime, with the control client's transport replaced but nothing else."""
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.path == "/health" and bounds is not None:
            return httpx.Response(
                HTTPStatus.OK,
                json={
                    "status": "ok",
                    "probe_timeout_s": bounds.probe_timeout_s,
                    "stop_grace_s": bounds.stop_grace_s,
                    "reap_timeout_s": bounds.reap_timeout_s,
                },
            )
        return httpx.Response(HTTPStatus.OK, json={"state": "ready", "detail": ""})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

    def mock_client(timeout_s: float) -> httpx.AsyncClient:
        del timeout_s
        return client

    monkeypatch.setattr(swap_builders, "build_control_client", mock_client)
    runtime = build_swap_runtime(
        _enabled(modelhost_backend="supervisor", modelhost_endpoint="http://model-host:9300"),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        lambda _url: _RecordingHandoffStore(released, refuse=refuse_store_close),
    )
    assert runtime is not None
    return runtime, client, asked


def test_escalation_is_off_by_default() -> None:
    config = SwapConfig()
    assert config.escalation is False
    assert config.modelhost_backend == "none"
    assert config.brain_model == "brain"


def test_the_tier_recheck_interval_is_read_from_the_deployments_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SWAP_TIER_HEAL_S", "7.5")
    assert SwapConfig().swap_tier_recheck_s == 7.5


def test_escalation_without_a_model_host_fails_at_boot() -> None:
    with pytest.raises(ValueError, match="CORTEX_MODELHOST_BACKEND must name a model host"):
        SwapConfig(escalation=True)


def test_escalation_without_a_brain_endpoint_fails_at_boot() -> None:
    with pytest.raises(ValueError, match="CORTEX_BRAIN_ENDPOINT is required"):
        SwapConfig(escalation=True, modelhost_backend="scripted")


def test_the_real_backend_without_its_endpoint_fails_at_boot() -> None:
    with pytest.raises(ValueError, match="CORTEX_MODELHOST_ENDPOINT is required"):
        _enabled(modelhost_backend="supervisor")


def test_the_residency_plan_carries_the_tier_ids_and_both_bounds() -> None:
    plan = _enabled(
        evict_models=("subagent-gpu",), swap_drain_timeout_s=5.0, swap_load_timeout_s=7.0
    ).residency_plan("cortex")
    assert (plan.cortex_model, plan.brain_model) == ("cortex", "brain")
    assert plan.evict_models == ("subagent-gpu",)
    assert (plan.drain_timeout_s, plan.load_timeout_s) == (5.0, 7.0)
    assert plan.coresident is False
    assert _enabled(coresident=True).residency_plan("cortex").coresident is True
    assert plan.brain_vram_mib == 0
    assert _enabled(brain_vram_mib=19125).residency_plan("cortex").brain_vram_mib == 19125
    assert plan.brain_decode_tps == 0.0
    assert _enabled(brain_decode_tps=22.0).residency_plan("cortex").brain_decode_tps == 22.0
    assert plan.control_deadline_s == SwapConfig().modelhost_timeout_s
    assert _enabled(modelhost_timeout_s=90.0).residency_plan("cortex").control_deadline_s == 90.0


def test_co_residency_on_the_real_host_without_a_measured_fit_fails_at_boot() -> None:
    with pytest.raises(ValueError, match="CORTEX_SWAP_BRAIN_VRAM_MIB is required"):
        _enabled(
            modelhost_backend="supervisor",
            modelhost_endpoint="http://model-host:9300",
            coresident=True,
        )


def test_co_residency_over_the_scripted_host_needs_no_measurement() -> None:
    plan = _enabled(coresident=True).residency_plan("cortex")
    assert (plan.coresident, plan.brain_vram_mib) == (True, 0)
    assert plan.brain_decode_tps == 0.0


def test_nothing_is_built_when_escalation_is_off() -> None:
    runtime = build_swap_runtime(
        SwapConfig(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is None


async def test_the_enabled_runtime_is_the_one_lease_and_the_one_residency() -> None:
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(backend="llamacpp", endpoint="http://llama-cortex:8080"),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    assert isinstance(runtime.manager, SwappingModelManager)
    assert isinstance(runtime.host, ScriptedModelHost)
    assert runtime.host.running == {"cortex"}
    async with runtime.manager.acquire("cortex") as lease:
        assert lease.endpoint == "http://llama-cortex:8080"
    async with runtime.manager.swap_scope("brain"), runtime.manager.acquire("brain") as lease:
        assert lease.endpoint == "http://llama-brain:8081"
    await swap_closer(runtime)()


async def test_each_tier_leases_the_endpoint_its_own_deployment_named() -> None:
    runtime = build_swap_runtime(
        _enabled(brain_model="brain-alt"),
        BrainRuntimeConfig(cortex_model="cortex-alt"),
        InferenceConfig(backend="llamacpp", endpoint="http://llama-cortex:8080"),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    plan = runtime.plan
    assert (plan.cortex_model, plan.brain_model) == ("cortex-alt", "brain-alt")
    async with runtime.manager.acquire(plan.cortex_model) as lease:
        assert lease.endpoint == "http://llama-cortex:8080"
    async with (
        runtime.manager.swap_scope(plan.brain_model),
        runtime.manager.acquire(plan.brain_model) as lease,
    ):
        assert lease.endpoint == "http://llama-brain:8081"
    await swap_closer(runtime)()


async def test_a_boot_whose_peer_tier_is_down_still_says_the_brain_is_ready() -> None:
    placer = VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)
    runtime = build_swap_runtime(
        _enabled(evict_models=("subagent-gpu",)),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
        placer,
    )
    assert runtime is not None
    broken = ScriptedModelHost(
        running=["cortex"], fail={("start", "subagent-gpu"): "no such device"}
    )
    try:
        await recover_boot_residency(replace(runtime, host=broken), SystemClock())
        await runtime.rechecker.aclose()
        report = runtime.manager.residency()
        assert report.serving is True
        assert report.detail == TIERS_MISSING_DETAIL.format(models="subagent-gpu")
        spawn = PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)
        assert placer.place(spawn).target is PlacementTarget.CPU
    finally:
        await swap_closer(runtime)()


async def test_the_supervisor_backend_builds_the_real_adapter_at_the_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, client, asked = _supervisor_runtime(monkeypatch, [])
    try:
        assert isinstance(runtime.host, HttpModelHost)
        assert await runtime.host.status("cortex") is ModelHostState.READY
    finally:
        await swap_closer(runtime)()
    assert asked == ["http://model-host:9300/models/cortex"]
    assert client.is_closed


async def test_the_control_client_has_a_read_deadline_unlike_the_generation_clients() -> None:
    client = swap_builders.build_control_client(31.5)
    try:
        assert client.timeout == httpx.Timeout(31.5)
    finally:
        await client.aclose()


async def test_closing_the_runtime_releases_the_control_client_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released: list[str] = []
    runtime, client, _ = _supervisor_runtime(monkeypatch, released)
    assert not client.is_closed
    await swap_closer(runtime)()
    assert released == ["handoff store"]
    assert client.is_closed


async def test_a_store_that_will_not_close_still_releases_the_control_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released: list[str] = []
    runtime, client, _ = _supervisor_runtime(monkeypatch, released, refuse_store_close=True)
    with pytest.raises(OSError, match="could not be released"):
        await swap_closer(runtime)()
    assert released == ["handoff store"]
    assert client.is_closed


async def test_the_closer_is_a_clean_no_op_when_nothing_was_built() -> None:
    await swap_closer(None)()


def _with_bounds(bounds: ControlBounds | None) -> SwapRuntime:
    """Build the scripted runtime, holding a host that reports ``bounds`` for its control calls."""
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    return replace(runtime, host=ScriptedModelHost(running=["cortex"], control_bounds=bounds))


def _only(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    """The single record the check emitted, so the shipped formatter can be run over it."""
    (record,) = caplog.records
    return record


async def test_the_shipped_bounds_and_the_shipped_deadline_still_clear_each_other() -> None:
    daemon = ModelHostConfig()
    shipped = ControlBounds(
        probe_timeout_s=daemon.probe_timeout_s,
        stop_grace_s=daemon.stop_grace_s,
        reap_timeout_s=daemon.reap_timeout_s,
    )
    assert shipped.worst_case_stop_s == 45.0
    assert shipped.clears(SwapConfig().modelhost_timeout_s) is True


async def test_a_deadline_the_hosts_worst_stop_can_outlast_refuses_to_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = _with_bounds(
        ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)
    )
    with caplog.at_level(logging.ERROR), pytest.raises(ControlDeadlineError) as excinfo:
        await check_control_deadline(runtime)
    assert "worst stop is 60.0 s (probe 5.0 s, grace 20.0 s, reap 35.0 s)" in str(excinfo.value)
    assert "CORTEX_MODELHOST_TIMEOUT_S is 60.0 s" in str(excinfo.value)
    # Asserted whole against the shipped formatter, because the swap runbook prints this line as
    # a sample and `samplecheck.py` compares that sample with a line a suite asserts whole.
    assert PlainFormatter().format(_only(caplog)) == (
        "ERROR:cortex_orchestrator.swap_builders:the control deadline does not clear the "
        "model host's worst stop deadline_s=60.0 probe_timeout_s=5.0 reap_timeout_s=35.0 "
        "stop_grace_s=20.0 worst_s=60.0"
    )


async def test_a_refused_pairing_releases_what_the_runtime_already_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released: list[str] = []
    runtime, client, asked = _supervisor_runtime(
        monkeypatch,
        released,
        bounds=ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0),
    )
    with pytest.raises(ControlDeadlineError):
        await check_control_deadline(runtime)
    assert asked == ["http://model-host:9300/health"]
    assert released == ["handoff store"]
    assert client.is_closed


async def test_a_deadline_that_clears_the_worst_stop_is_wired_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = _with_bounds(
        ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
    )
    with caplog.at_level(logging.INFO):
        await check_control_deadline(runtime)
    assert "clears the model host's worst stop" in caplog.text
    assert "deadline_s=60.0 worst_s=45.0" in PlainFormatter().format(_only(caplog))
    await swap_closer(runtime)()


async def test_a_host_that_bounds_no_stop_of_its_own_is_not_a_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = _with_bounds(None)
    with caplog.at_level(logging.INFO):
        await check_control_deadline(runtime)
    assert "reports no control bounds" in caplog.text
    await swap_closer(runtime)()


async def test_a_host_that_cannot_be_asked_leaves_the_pairing_unchecked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = build_swap_runtime(
        _enabled(),
        BrainRuntimeConfig(),
        InferenceConfig(),
        SystemClock(),
        AsyncioSleeper(),
        _fake_handoff_store,
    )
    assert runtime is not None
    unreachable = ScriptedModelHost(fail={("control_bounds", ""): "connection refused"})
    with caplog.at_level(logging.WARNING):
        await check_control_deadline(replace(runtime, host=unreachable))
    assert "could not be asked for its control bounds" in caplog.text
    await swap_closer(runtime)()


async def test_the_pairing_check_is_a_clean_no_op_when_nothing_was_built() -> None:
    await check_control_deadline(None)


async def test_the_escalate_tool_is_not_advertised_unless_a_handoff_can_run() -> None:
    without = build_builtin_tools(None, InMemoryBodyGateway())
    assert [tool.spec.name for tool in without if tool.spec.name == ESCALATE_TOOL_NAME] == []
    with_handoff = build_builtin_tools(None, InMemoryBodyGateway(), escalation=True)
    assert ESCALATE_TOOL_NAME in [tool.spec.name for tool in with_handoff]


async def test_run_from_env_serves_with_the_handoff_wired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        events = await _run_one_turn(f"127.0.0.1:{port}")
        assert (
            "".join(
                event.text_delta.text
                for event in events
                if event.WhichOneof("event") == "text_delta"
            )
            == "reply 1: hello"
        )
        assert any(event.WhichOneof("event") == "turn_complete" for event in events)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_run_from_env_refuses_a_deployment_whose_pairing_does_not_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "supervisor")
    monkeypatch.setenv("CORTEX_MODELHOST_ENDPOINT", "http://model-host:9300")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    def handle(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            HTTPStatus.OK,
            json={
                "status": "ok",
                "probe_timeout_s": 5.0,
                "stop_grace_s": 20.0,
                "reap_timeout_s": 35.0,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

    def mock_client(timeout_s: float) -> httpx.AsyncClient:
        del timeout_s
        return client

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "build_control_client", mock_client)
    with pytest.raises(ControlDeadlineError, match=r"CORTEX_MODELHOST_TIMEOUT_S is 60\.0 s"):
        await asyncio.wait_for(
            run_from_env(store_factory=lambda _url: _session_store(server)), timeout=10
        )
    assert client.is_closed


async def test_health_tells_the_truth_about_residency_through_the_whole_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    built: list[SwapRuntime] = []
    real = build_swap_runtime

    def recording(  # noqa: PLR0913 -- mirrors the builder it stands in for
        swap: SwapConfig,
        runtime: BrainRuntimeConfig,
        inference: InferenceConfig,
        clock: Clock,
        sleeper: Sleeper,
        handoff_store_factory: Callable[[str], RedisHandoffStore] = RedisHandoffStore.from_url,
        placer: SubagentPlacer | None = None,
    ) -> SwapRuntime | None:
        made = real(swap, runtime, inference, clock, sleeper, handoff_store_factory, placer)
        assert made is not None
        built.append(made)
        return made

    monkeypatch.setattr(wiring, "build_swap_runtime", recording)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            assert (await _health(stub)).ready is True
            swap = built[0]
            async with swap.manager.swap_scope(swap.plan.brain_model):
                mid_handoff = await asyncio.wait_for(_health(stub), timeout=5.0)
            assert mid_handoff.ready is False
            assert mid_handoff.detail == RESIDENCY_DEEP.detail
            assert (await _health(stub)).ready is True
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_a_boot_that_could_not_settle_the_cortex_leaves_the_rpc_saying_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    monkeypatch.setenv("CORTEX_SWAP_LOAD_TIMEOUT_S", "0")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "ScriptedModelHost", _stuck_host)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            reply = await asyncio.wait_for(_health(BrainServiceStub(channel)), timeout=5.0)
        assert reply.ready is False
        assert reply.detail == RESIDENCY_BOOT_FAILED.detail
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def test_a_cortex_that_comes_up_after_the_boot_result_turns_the_rpc_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _free_loopback_port()
    monkeypatch.setenv("CORTEX_SEAM_HOST", "127.0.0.1")
    monkeypatch.setenv("CORTEX_SEAM_PORT", str(port))
    monkeypatch.setenv("CORTEX_ESCALATION", "1")
    monkeypatch.setenv("CORTEX_MODELHOST_BACKEND", "scripted")
    monkeypatch.setenv("CORTEX_BRAIN_ENDPOINT", "http://llama-brain:8081")
    monkeypatch.setenv("CORTEX_SWAP_LOAD_TIMEOUT_S", "0")
    monkeypatch.setenv("CORTEX_SWAP_TIER_HEAL_S", "0.01")
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    hosts: list[ScriptedModelHost] = []

    def remembered(*, running: Iterable[str]) -> ScriptedModelHost:
        hosts.append(_stuck_host(running=running))
        return hosts[-1]

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    monkeypatch.setattr(swap_builders, "ScriptedModelHost", remembered)
    task = asyncio.create_task(run_from_env(store_factory=lambda _url: _session_store(server)))
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            await asyncio.wait_for(channel.channel_ready(), timeout=10)
            stub = BrainServiceStub(channel)
            assert (await asyncio.wait_for(_health(stub), timeout=5.0)).ready is False
            for model in sorted(hosts[0].running):
                hosts[0].set_status(model, None)
            async with asyncio.timeout(10):
                while not (await _health(stub)).ready:  # noqa: ASYNC110 -- no event to wait on
                    await asyncio.sleep(0.01)
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, timeout=10)
    finally:
        task.cancel()


async def _health(stub: BrainServiceStub) -> HealthReply:
    health = stub.Health  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast("HealthReply", await health(HealthRequest()))


def _session_store(server: FakeServer) -> RedisSessionStore:
    return RedisSessionStore(FakeAsyncRedis(server=server))


async def _run_one_turn(address: str) -> list[ServerEvent]:
    async with aio.insecure_channel(address) as channel:
        await asyncio.wait_for(channel.channel_ready(), timeout=10)
        stub = BrainServiceStub(channel)
        converse = stub.Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", converse())
        await call.write(ClientEvent(session_id="wired", user_turn=UserTurn(text="hello")))
        await call.done_writing()
        return [event async for event in call]
