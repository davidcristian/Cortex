import asyncio
import os
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from cortex_core import (
    RESIDENCY_DEEP,
    RESIDENCY_SERVING,
    AsyncioSleeper,
    ModelHostError,
    ModelHostState,
    ModelNotHostedError,
    Placement,
    PlacementRequest,
    PlacementTarget,
    ResidencyPlan,
    SwapFailedError,
    SwappingModelManager,
    VramBudgetPlacer,
    await_model_ready,
)
from cortex_core.residency_moves import swap_in
from cortex_model_manager import (
    AsyncioChildProcesses,
    ChildProcess,
    HttpModelHost,
    ModelSpec,
    ModelSupervisor,
    build_roster,
)
from cortex_model_manager.probe import HttpHealthProbe

_MODEL = "stand-in"
_GRACE_S = 0.5
# How long the trapping shell gets to install its trap before the test gives up rather than
# hanging.
_ARM_TIMEOUT_S = 5.0
# The control plane's own deadline, matching the brain's CORTEX_MODELHOST_TIMEOUT_S default: a
# stop answers only once the child is reaped, so this must clear the sidecar's grace and reap
# bounds together.
_CONTROL_TIMEOUT_S = 60.0
# The deep tier's measured cost and a subagent ask, each in the units its own setting uses
# (CORTEX_SWAP_BRAIN_VRAM_MIB, CORTEX_SUBAGENTS_VRAM_GB). The ask is held at the figure that
# straddles the handoff window rather than tracking the shipped default, which would fit both.
_DEEP_TIER_MIB = 19125
_SPAWN_GB = 5.5


class _SystemClock:
    """The real clock, for the live run only: the other suites all inject a deterministic one."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class _RecordingProcesses:
    """The real spawner, remembering its children so a test can read their real exit codes."""

    def __init__(self) -> None:
        self._real = AsyncioChildProcesses()
        self.children: list[ChildProcess] = []

    async def spawn(self, argv: Sequence[str]) -> ChildProcess:
        child = await self._real.spawn(argv)
        self.children.append(child)
        return child


def _supervisor(command: str) -> tuple[ModelSupervisor, _RecordingProcesses]:
    """Build a supervisor whose one model is a shell command: the OS half real, the model not."""
    roster = build_roster(
        [ModelSpec(model=_MODEL, port=8099, argv=("/bin/sh", "-c", command, "--port", "8099"))]
    )
    processes = _RecordingProcesses()
    probe = HttpHealthProbe(httpx.AsyncClient(timeout=httpx.Timeout(1.0)))
    return (
        ModelSupervisor(roster, processes, probe, stop_grace_s=_GRACE_S, reap_timeout_s=5.0),
        processes,
    )


@pytest.mark.integration
async def test_a_real_child_is_started_signalled_and_reaped() -> None:
    supervisor, processes = _supervisor("sleep 30")
    await supervisor.start(_MODEL)
    child = processes.children[0]
    assert child.returncode is None
    assert (await supervisor.status(_MODEL)).state is ModelHostState.LOADING
    await supervisor.stop(_MODEL)
    assert child.returncode is not None
    assert (await supervisor.status(_MODEL)).state is ModelHostState.STOPPED


@pytest.mark.integration
async def test_a_real_child_that_ignores_sigterm_is_killed_after_the_grace(tmp_path: Path) -> None:
    armed = tmp_path / "armed"
    supervisor, processes = _supervisor(f'trap "" TERM; : > {armed}; sleep 30')
    await supervisor.start(_MODEL)
    async with asyncio.timeout(_ARM_TIMEOUT_S):
        while not armed.exists():  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    child = processes.children[0]
    await supervisor.stop(_MODEL)
    assert child.returncode == -9
    assert (await supervisor.status(_MODEL)).state is ModelHostState.STOPPED


@pytest.mark.integration
async def test_the_real_adapter_starts_health_gates_and_stops_a_real_model() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    model = os.environ.get("CORTEX_MODELHOST_LIVE_MODEL", "cortex")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    plan = ResidencyPlan(cortex_model=model, brain_model=model, load_timeout_s=300.0)
    try:
        await host.stop(model)
        assert await host.status(model) is ModelHostState.STOPPED
        await host.start(model)
        state = await await_model_ready(
            host, model, clock=_SystemClock(), sleeper=AsyncioSleeper(), plan=plan
        )
        assert state is ModelHostState.READY
        await host.stop(model)
        assert await host.status(model) is ModelHostState.STOPPED
    finally:
        await host.start(model)
        await client.aclose()


@pytest.mark.integration
async def test_a_residency_scope_really_evicts_one_model_and_loads_another() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    deep = os.environ.get("CORTEX_MODEL_BRAIN", "brain")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    plan = ResidencyPlan(cortex_model=standing, brain_model=deep, load_timeout_s=300.0)
    manager = SwappingModelManager(
        host,
        {standing: "http://127.0.0.1:8080", deep: "http://127.0.0.1:8081"},
        plan,
        _SystemClock(),
        AsyncioSleeper(),
    )
    try:
        try:
            deep_state = await host.status(deep)
        except ModelHostError as err:
            pytest.skip(f"the sidecar does not host a deep tier {deep!r}: {err}")
        if deep_state is ModelHostState.FAILED:
            pytest.skip(f"the deep tier {deep!r} has a dead child; fix it before swapping onto it")
        await host.start(standing)
        assert manager.residency() == RESIDENCY_SERVING
        async with manager.swap_scope(deep):
            assert await host.status(deep) is ModelHostState.READY
            assert await host.status(standing) is ModelHostState.STOPPED
            assert manager.residency() == RESIDENCY_DEEP
            async with manager.acquire(deep) as lease:
                assert lease.endpoint == "http://127.0.0.1:8081"
        assert await host.status(standing) is ModelHostState.READY
        assert await host.status(deep) is ModelHostState.STOPPED
        assert manager.residency() == RESIDENCY_SERVING
    finally:
        await client.aclose()


@pytest.mark.integration
async def test_a_coresident_scope_leaves_its_peer_serving_beside_the_deep_model() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    deep = os.environ.get("CORTEX_MODEL_BRAIN", "brain")
    peer = os.environ.get("CORTEX_MODEL_SUBAGENT_GPU", "subagent-gpu")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    plan = ResidencyPlan(
        cortex_model=standing,
        brain_model=deep,
        evict_models=(peer,),
        coresident=True,
        load_timeout_s=300.0,
    )
    manager = SwappingModelManager(
        host,
        {standing: "http://127.0.0.1:8080", deep: "http://127.0.0.1:8081"},
        plan,
        _SystemClock(),
        AsyncioSleeper(),
    )
    try:
        try:
            states = [await host.status(model) for model in (deep, peer)]
        except ModelHostError as err:
            pytest.skip(f"the sidecar does not host both {deep!r} and {peer!r}: {err}")
        if ModelHostState.FAILED in states:
            pytest.skip(f"a tier in {(deep, peer)} has a dead child; fix it before swapping")
        await host.start(standing)
        await host.start(peer)
        assert await _settled(host, peer) is ModelHostState.READY
        async with manager.swap_scope(deep):
            assert await host.status(deep) is ModelHostState.READY
            assert await host.status(standing) is ModelHostState.STOPPED
            assert await host.status(peer) is ModelHostState.READY
        assert await host.status(standing) is ModelHostState.READY
        assert await host.status(peer) is ModelHostState.READY
    finally:
        await client.aclose()


@pytest.mark.integration
async def test_a_stock_sidecar_answers_the_escalation_precondition_without_touching_a_thing() -> (
    None
):
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    deep = os.environ.get("CORTEX_MODEL_BRAIN", "brain")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    plan = ResidencyPlan(cortex_model=standing, brain_model=deep, load_timeout_s=300.0)
    manager = SwappingModelManager(
        host,
        {standing: "http://127.0.0.1:8080", deep: "http://127.0.0.1:8081"},
        plan,
        _SystemClock(),
        AsyncioSleeper(),
    )
    try:
        try:
            await host.status(deep)
        except ModelNotHostedError:
            pass
        else:
            pytest.skip(f"the sidecar hosts a deep tier {deep!r}, so there is nothing to refuse")
        await host.start(standing)
        assert await _settled(host, standing) is ModelHostState.READY
        assert await manager.unhosted(deep) is True
        assert await host.status(standing) is ModelHostState.READY
        assert manager.residency() == RESIDENCY_SERVING
    finally:
        await client.aclose()


async def _settled(host: HttpModelHost, model: str) -> ModelHostState:
    """Wait out a tier's load, so a peer started for this test is judged once it is serving."""
    return await await_model_ready(
        host,
        model,
        clock=_SystemClock(),
        sleeper=AsyncioSleeper(),
        plan=ResidencyPlan(cortex_model=model, brain_model=model, load_timeout_s=300.0),
    )


@pytest.mark.integration
async def test_the_real_sidecar_reports_the_card_it_can_see() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    try:
        reading = await HttpModelHost(endpoint, client).device_memory()
    finally:
        await client.aclose()
    if reading is None:
        pytest.skip("this model-host container can see no GPU, so there is no reading to check")
    assert 0 < reading.free_mib <= reading.total_mib


@pytest.mark.integration
async def test_a_swap_refuses_the_load_the_card_has_no_room_for_and_allows_the_one_it_has() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    target = os.environ.get("CORTEX_MODELHOST_LIVE_FIT_MODEL", "subagent-gpu")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    found_running = False
    try:
        try:
            found_running = await host.status(target) is not ModelHostState.STOPPED
        except ModelHostError as err:
            pytest.skip(f"the sidecar does not host {target!r}: {err}")
        await host.stop(target)
        reading = await host.device_memory()
        if reading is None:
            pytest.skip("this model-host container can see no GPU, so no fit can be checked")
        gate = _gate_for(host)
        with pytest.raises(SwapFailedError, match=f"only {reading.free_mib} of "):
            await swap_in(host, _fit_plan(target, reading.free_mib + 1), target, gate)
        assert await host.status(target) is ModelHostState.STOPPED
        await swap_in(host, _fit_plan(target, reading.free_mib), target, gate)
        assert await host.status(target) is ModelHostState.READY
    finally:
        if found_running:
            await host.start(target)
        else:
            await host.stop(target)
        await client.aclose()


@pytest.mark.integration
async def test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    target = os.environ.get("CORTEX_MODELHOST_LIVE_FIT_MODEL", "subagent-gpu")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    placer = VramBudgetPlacer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    plan = ResidencyPlan(
        cortex_model=standing,
        brain_model=target,
        coresident=True,
        brain_vram_mib=_DEEP_TIER_MIB,
        load_timeout_s=300.0,
    )
    manager = SwappingModelManager(
        host,
        {standing: "http://127.0.0.1:8080", target: "http://127.0.0.1:8083"},
        plan,
        _SystemClock(),
        AsyncioSleeper(),
        placer,
    )
    try:
        try:
            await host.status(target)
        except ModelHostError as err:
            pytest.skip(f"the sidecar does not host {target!r}: {err}")
        await host.start(standing)
        assert await _settled(host, standing) is ModelHostState.READY
        before = await host.device_memory()
        if before is None:
            pytest.skip("this model-host container can see no GPU, so no charge can be grounded")
        assert placer.place(_spawn()).target is PlacementTarget.GPU
        placer.release(Placement(target=PlacementTarget.GPU, reserved_gb=_SPAWN_GB))
        async with manager.swap_scope(target):
            inside = await host.device_memory()
            assert inside is not None
            print(  # noqa: T201 -- the raw numbers are the point of a live run
                f"\nfree before the swap: {before.free_mib} of {before.total_mib} MiB"
                f"\nfree inside the window: {inside.free_mib} MiB"
                f"\ncharged: {plan.brain_vram_gb:.2f} GiB, headroom "
                f"{23.0 - plan.brain_vram_gb:.2f} GiB against a {_SPAWN_GB} GiB ask"
            )
            assert placer.place(_spawn()).target is PlacementTarget.CPU
        assert placer.place(_spawn()).target is PlacementTarget.GPU
    finally:
        await host.stop(target)
        await host.start(standing)
        await client.aclose()


@pytest.mark.integration
async def test_a_background_pass_regains_residency_from_the_real_sidecar() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    deep = os.environ.get("CORTEX_MODEL_BRAIN", "brain")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    manager = _live_manager(host, standing, deep)
    try:
        await host.start(standing)
        if await _settled(host, standing) is not ModelHostState.READY:
            pytest.skip(f"the cortex tier {standing!r} is not serving; fix that before this test")
        await manager.publish_boot_residency(serving=False)
        assert manager.residency().serving is False
        before = list(await _tier_states(host, (standing, deep)))
        await manager.heal_residency()
        assert manager.residency() == RESIDENCY_SERVING
        async with manager.acquire(standing) as lease:
            assert lease.endpoint == "http://127.0.0.1:8080"
        assert list(await _tier_states(host, (standing, deep))) == before
    finally:
        await client.aclose()


@pytest.mark.integration
async def test_a_real_deep_tier_on_the_card_stops_the_regain() -> None:
    endpoint = os.environ.get("CORTEX_MODELHOST_ENDPOINT")
    if not endpoint:
        pytest.skip("set CORTEX_MODELHOST_ENDPOINT to a running model-host sidecar")
    standing = os.environ.get("CORTEX_MODEL_CORTEX", "cortex")
    deep = os.environ.get("CORTEX_MODEL_BRAIN", "brain")
    client = httpx.AsyncClient(timeout=httpx.Timeout(_CONTROL_TIMEOUT_S))
    host = HttpModelHost(endpoint, client)
    manager = _live_manager(host, standing, deep)
    try:
        try:
            await host.start(deep)
        except ModelHostError as err:
            pytest.skip(f"the sidecar does not host a deep tier {deep!r}: {err}")
        try:
            await host.start(standing)
            if (await _settled(host, deep), await _settled(host, standing)) != (
                ModelHostState.READY,
                ModelHostState.READY,
            ):
                pytest.skip("this card could not hold both tiers, so there is no guard to test")
            await manager.publish_boot_residency(serving=False)
            await manager.heal_residency()
            assert manager.residency().serving is False
            await host.stop(deep)
            await manager.heal_residency()
            assert manager.residency() == RESIDENCY_SERVING
        finally:
            await host.stop(deep)
            await host.start(standing)
    finally:
        await client.aclose()


def _live_manager(host: HttpModelHost, standing: str, deep: str) -> SwappingModelManager:
    """Build the shipped manager over the real adapter, on the loopback override's endpoints."""
    return SwappingModelManager(
        host,
        {standing: "http://127.0.0.1:8080", deep: "http://127.0.0.1:8081"},
        ResidencyPlan(cortex_model=standing, brain_model=deep, load_timeout_s=300.0),
        _SystemClock(),
        AsyncioSleeper(),
    )


async def _tier_states(host: HttpModelHost, models: Sequence[str]) -> list[str]:
    """Return what the sidecar says each tier is doing, reading a 404 as a tier it does not host."""
    states: list[str] = []
    for model in models:
        try:
            states.append((await host.status(model)).value)
        except ModelNotHostedError:
            states.append("unhosted")
    return states


def _spawn() -> PlacementRequest:
    """Build one spawn asking for the shipped subagent VRAM budget."""
    return PlacementRequest("subagent", vram_gb=_SPAWN_GB, cpus=1.0, memory_gb=2.0)


def _fit_plan(target: str, needed_mib: int) -> ResidencyPlan:
    """Build a plan whose resident model is the target itself, so nothing else is evicted."""
    return ResidencyPlan(
        cortex_model=target, brain_model=target, brain_vram_mib=needed_mib, load_timeout_s=300.0
    )


def _gate_for(host: HttpModelHost) -> Callable[[str], Awaitable[ModelHostState]]:
    """The real readiness check, bound to this host, as the manager binds its own."""

    async def gate(model: str) -> ModelHostState:
        return await _settled(host, model)

    return gate
