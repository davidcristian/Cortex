"""Live halves of the model host: real child processes, and a real sidecar over real HTTP."""

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
# How long the trapping shell gets to arm itself before the test gives up rather than hanging.
_ARM_TIMEOUT_S = 5.0
# The control plane's own deadline, matching the brain's CORTEX_MODELHOST_TIMEOUT_S default: a stop
# answers only once the child is reaped, so this must clear the sidecar's grace plus reap bounds.
_CONTROL_TIMEOUT_S = 60.0
_DEEP_TIER_MIB = 19125
_SPAWN_GB = 5.5


class _SystemClock:
    """The real clock, for the live gate only: the gated suites all inject a deterministic one."""

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
    """A supervisor whose one model is a shell command: the OS half real, the model not."""
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
    """SIGTERM reaches a real process, and the stop returns only once the OS has reaped it."""
    supervisor, processes = _supervisor("sleep 30")
    await supervisor.start(_MODEL)
    child = processes.children[0]
    assert child.returncode is None
    # Nothing serves /health on that port, so an alive child reads as still loading. That is the
    # honest state of every llama-server for the first seconds of its life.
    assert (await supervisor.status(_MODEL)).state is ModelHostState.LOADING
    await supervisor.stop(_MODEL)
    assert child.returncode is not None
    assert (await supervisor.status(_MODEL)).state is ModelHostState.STOPPED


@pytest.mark.integration
async def test_a_real_child_that_ignores_sigterm_is_killed_after_the_grace(tmp_path: Path) -> None:
    """The bounded escalation, against a process that genuinely traps the signal."""
    armed = tmp_path / "armed"
    supervisor, processes = _supervisor(f'trap "" TERM; : > {armed}; sleep 30')
    await supervisor.start(_MODEL)
    async with asyncio.timeout(_ARM_TIMEOUT_S):
        # The suppressed rule wants an asyncio.Event, which cannot observe a file that another
        # process creates; the enclosing timeout is what keeps the poll from becoming a hang.
        while not armed.exists():  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    child = processes.children[0]
    await supervisor.stop(_MODEL)
    assert child.returncode == -9
    assert (await supervisor.status(_MODEL)).state is ModelHostState.STOPPED


@pytest.mark.integration
async def test_the_real_adapter_starts_health_gates_and_stops_a_real_model() -> None:
    """The mechanism against a running sidecar: a real llama-server up, then genuinely gone."""
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
        # Leave the tier this ran against loaded, which is the sidecar's boot default when the
        # model is the standing resident (the default) and is the caller's to undo when it is not.
        await host.start(model)
        await client.aclose()


@pytest.mark.integration
async def test_a_residency_scope_really_evicts_one_model_and_loads_another() -> None:
    """The swap, over real weights: the closest thing to a handoff that fits the dev GPU."""
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
            # The gate inside swap_scope already waited for READY; what is asserted here is the
            # eviction half, which nothing else would catch: a swap that loaded the deep model
            # without stopping the standing one would leave both processes alive.
            assert await host.status(deep) is ModelHostState.READY
            assert await host.status(standing) is ModelHostState.STOPPED
            # And what the seam would tell a probing overlay right now matches those two reads.
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
    """The opt-in reversal, over real weights: the peer tier never leaves the card."""
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
            # The whole point: the peer was never asked to leave, so it is serving beside the
            # deep model rather than waiting to be restarted after it.
            assert await host.status(peer) is ModelHostState.READY
        assert await host.status(standing) is ModelHostState.READY
        assert await host.status(peer) is ModelHostState.READY
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
    """The reading the fit check rests on, taken through the real adapter off a real driver."""
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
    """Both sides of the fit check against one real card, one real sidecar, one real load."""
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
        # One MiB more than the card has free: nothing may be started, and the message has to
        # carry both figures, since that is all an operator gets to diagnose it with.
        with pytest.raises(SwapFailedError, match=f"only {reading.free_mib} of "):
            await swap_in(host, _fit_plan(target, reading.free_mib + 1), target, gate)
        assert await host.status(target) is ModelHostState.STOPPED
        # Exactly what is free: the same call, the same card, and this one really loads.
        await swap_in(host, _fit_plan(target, reading.free_mib), target, gate)
        assert await host.status(target) is ModelHostState.READY
    finally:
        # Leave the sidecar as it was found, on every path this can take: a start is idempotent,
        # so it is a no-op against the tier the second arm just loaded and a restore for one an
        # early skip left stopped.
        if found_running:
            await host.start(target)
        else:
            await host.stop(target)
        await client.aclose()


@pytest.mark.integration
async def test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card() -> None:
    """The handoff window's arithmetic, against a real residency change and a real card reading."""
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


def _spawn() -> PlacementRequest:
    """One spawn asking for the shipped subagent VRAM budget."""
    return PlacementRequest("subagent", vram_gb=_SPAWN_GB, cpus=1.0, memory_gb=2.0)


def _fit_plan(target: str, needed_mib: int) -> ResidencyPlan:
    """A plan whose standing resident is the target itself, so nothing else is evicted."""
    return ResidencyPlan(
        cortex_model=target, brain_model=target, brain_vram_mib=needed_mib, load_timeout_s=300.0
    )


def _gate_for(host: HttpModelHost) -> Callable[[str], Awaitable[ModelHostState]]:
    """The real readiness gate, bound to this host, as the manager binds its own."""

    async def gate(model: str) -> ModelHostState:
        return await _settled(host, model)

    return gate
