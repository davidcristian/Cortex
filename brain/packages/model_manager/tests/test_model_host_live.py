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
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from cortex_core import (
    AsyncioSleeper,
    ModelHostState,
    ResidencyPlan,
    SwappingModelManager,
    await_model_ready,
)
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
    gate against two ``llama-server`` processes, and leaving it runs the real restore. What it
    asserts is read back from the sidecar through the port, never from the manager's own
    bookkeeping: inside the scope the deep tier's process is READY and the standing resident's is
    gone, and after it the reverse.

    Needs two tiers in the roster (name a ``CORTEX_MODEL_FILE_BRAIN`` artifact) and enough VRAM for
    whichever pair the deployment configured; on the dev GPU that means small stand-ins, and it is
    skipped rather than failed when the deep tier is not hosted.
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
        if await host.status(deep) is ModelHostState.FAILED:
            pytest.skip(f"the deep tier {deep!r} is not hosted (no artifact named for it)")
        await host.start(standing)
        async with manager.swap_scope(deep):
            # The gate inside swap_scope already waited for READY; what is asserted here is the
            # eviction half, which nothing else would catch: a swap that loaded the deep model
            # without stopping the standing one would leave both processes alive.
            assert await host.status(deep) is ModelHostState.READY
            assert await host.status(standing) is ModelHostState.STOPPED
            async with manager.acquire(deep) as lease:
                assert lease.endpoint == "http://127.0.0.1:8081"
        assert await host.status(standing) is ModelHostState.READY
        assert await host.status(deep) is ModelHostState.STOPPED
    finally:
        await client.aclose()
