"""Live halves of the model host: real child processes, and a real sidecar over real HTTP."""

import os
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
import pytest

from cortex_core import (
    AsyncioSleeper,
    ModelHostState,
    ResidencyPlan,
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
async def test_a_real_child_that_ignores_sigterm_is_killed_after_the_grace() -> None:
    """The bounded escalation, against a process that genuinely traps the signal."""
    supervisor, processes = _supervisor('trap "" TERM; sleep 30')
    await supervisor.start(_MODEL)
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
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
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
        # Leave the sidecar as its boot default has it: the standing resident serving.
        await host.start(model)
        await client.aclose()
