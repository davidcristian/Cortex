"""Live halves of the model host: real child processes, and a real sidecar over real HTTP.

``integration``-marked, so the workspace addopts (``-m "not integration"``) keep them out of CI and
out of the coverage gate (AGENTS.md gate 3). Run them on a host:

    cd brain && uv run pytest -m integration --no-cov packages/model_manager

The first test needs nothing but a POSIX shell: it drives the real ``AsyncioChildProcesses`` and
the real signal escalation against processes that actually exist, which is the half a fake child
cannot prove (that SIGTERM reaches a real process, that a process ignoring it is killed, and that
``stop`` does not return until the OS has reaped it).

The remaining two need the ``model-host`` sidecar up with the control API reachable:

    just up-modelhost-loopback
    just brain-modelhost-live

The first of those starts, health-gates and stops one real ``llama-server`` through the real
adapter and the real health gate. The second is the swap itself: a real ``SwappingModelManager``
residency scope over the real adapter, so entering the scope genuinely evicts one model's process
and loads another's, and leaving it genuinely restores the first. Both leave the sidecar as they
found it, and neither asserts anything about VRAM arithmetic or tier scale: the dev GPU cannot
hold the real cortex beside a real deep model, so that half is host-side by design
(``docs/runbooks/model-swap.md``).

Distrust-green, measured against the running sidecar rather than argued: deleting
``residency_moves.swap_in``'s ``stop`` of the standing resident reddens
``test_a_residency_scope_really_evicts_one_model_and_loads_another`` with both tiers reporting READY
at once, which is the eviction half nothing else here would catch.
"""

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
    ResidencyPlan,
    SwapFailedError,
    SwappingModelManager,
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
    """The bounded escalation, against a process that genuinely traps the signal.

    The wait for the marker is not padding: ``start`` returns as soon as the process exists, which
    is before the shell has run ``trap``, and a SIGTERM delivered in that window lands on the
    default disposition and the child dies with -15. That would pass a weaker assertion while
    testing the opposite case, so the child says when it is armed and the test waits for it.
    """
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
    """The swap, over real weights: the closest thing to a handoff that fits the dev GPU.

    Drives the shipped ``SwappingModelManager`` (the same object the conductor drives) over the
    real adapter, so entering the scope runs the real eviction, the real spawn and the real health
    gate against two ``llama-server`` processes, and leaving it runs the real restore. The swap
    itself is asserted by reading the sidecar back through the port, never from the manager's own
    bookkeeping: inside the scope the deep tier's process is READY and the standing resident's is
    gone, and after it the reverse.

    The residency report the seam answers ``Health`` with is then checked **against** those reads,
    which is the only place that pairing is made over real processes: the brain claiming a deep
    task is in progress is worth exactly as much as the deep child really being the one alive.

    Needs two tiers in the roster (name a ``CORTEX_MODEL_FILE_BRAIN`` artifact) and enough VRAM for
    whichever pair the deployment configured; on the dev GPU that means small stand-ins. On the
    shipped defaults no deep artifact is named, so the tier is not in the roster at all and the
    sidecar answers **404** for it: that is a ``ModelHostError`` from the adapter, never
    ``ModelHostState.FAILED``, which means "a hosted tier whose child died". Both are skips here,
    for different reasons, and the 404 one is the case a stock stack actually hits.
    """
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
    """The opt-in reversal, over real weights: the peer tier never leaves the card.

    The same real path as the eviction case above, one plan field apart. With ``coresident`` set,
    entering the scope must stop the standing resident and nothing else, so the GPU-placed
    subagent tier is still READY while the deep model serves, and it is still READY after the
    restore without anything having restarted it. That last read is the one that separates a tier
    kept alive from a tier evicted and put back: a swap that stopped it would also restart it, so
    the assertion that catches the difference is the one taken INSIDE the scope.

    Needs three tiers in the roster (``CORTEX_MODEL_FILE_BRAIN`` and
    ``CORTEX_MODEL_FILE_SUBAGENT_GPU`` both named) and a card that holds the deep model and the
    peer at once, which is what the deployment asserts by setting the flag at all. Every other
    shape skips.
    """
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
    """The reading the fit check rests on, taken through the real adapter off a real driver.

    Asserted as a shape rather than a number, because the figure is the machine's and moves while
    the desktop runs; what a gated test cannot reach at all is whether the sidecar's container can
    see a GPU, which is the entire premise of checking a fit from the brain.
    """
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
    """Both sides of the fit check against one real card, one real sidecar, one real load.

    The two arms differ in **one number** and nothing else: the same target tier, the same moment,
    the same free memory. Asking for a megabyte more than the card has free must refuse without
    starting anything, and asking for exactly what is free must go through and really load. That
    pairing is what makes this a check rather than a switch, and the refusal arm is the one no
    gated test can prove, because only a real driver can say what is genuinely free.

    Deliberately driven through ``swap_in`` rather than a residency scope: a scope's ``finally``
    restores the standing resident, which on a refusal would reload a tier the swap never touched
    and cost minutes to prove nothing. The plan therefore names a stopped tier as its standing
    resident, so the eviction step is a no-op and what is measured is the check alone.

    The target has to start this stopped, because the card's free figure is read once and both
    arms are judged against it. A target the co-residency case above left serving is stopped here
    and started again on the way out, rather than skipping: this is the one case whose whole
    subject is what the card has free, so it may not be the case that quietly does not run.
    """
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
