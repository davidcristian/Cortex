"""The supervisor's own rules, beyond what the shared port contract can observe.

The contract suite pins what a ``ModelHost`` must answer; these pin how this one gets there: one
process per model however many starts arrive, a signal escalation that is bounded, a stop that
does not return early, and a failure that keeps reporting a process it could not kill. Every wait
here is a fraction of a second and driven by a fake child, so nothing sleeps for a real grace.

Distrust-green proofs, each applied to production code alone with the whole
``packages/model_manager`` suite re-run, so the counts are measured:

- deleting the child from ``_children`` **before** ``_end`` reddens 9 cases, including
  ``test_a_child_that_survives_sigkill_keeps_being_reported`` and
  ``test_stop_does_not_return_until_the_child_is_reaped`` here, three of the shared contract's
  supervisor cases, and two in ``test_api.py``;
- returning from ``stop`` without awaiting the child's exit (signalling and moving on) reddens 5
  cases: ``test_stop_does_not_return_until_the_child_is_reaped``,
  ``test_a_wedged_child_is_killed_after_the_grace``,
  ``test_a_child_that_survives_sigkill_keeps_being_reported``,
  ``test_stop_all_stops_every_model_and_survives_one_that_will_not_die``, and the api suite's 503
  case;
- skipping the SIGKILL escalation (returning after the grace instead) reddens 4 cases: the three
  stop cases here plus the api suite's 503 case;
- dropping the per-model lock from ``start`` reddens exactly 1,
  ``test_two_concurrent_starts_spawn_one_process``, which is why the fake suspends inside its spawn
  rather than merely counting calls.
"""

import asyncio

import pytest
from model_host_contract import CORTEX, DEEP
from process_fakes import FakeChildProcesses, FakeProbe
from test_model_host_contract import contract_roster

from cortex_core import ModelHostState
from cortex_model_manager import ModelStatus, ModelSupervisor, SupervisorError, UnknownModelError

_TINY = 0.05


def _supervisor(
    processes: FakeChildProcesses | None = None, probe: FakeProbe | None = None
) -> tuple[ModelSupervisor, FakeChildProcesses, FakeProbe]:
    """A supervisor over the contract roster with sub-second bounds, plus its two fakes."""
    children = processes or FakeChildProcesses()
    health = probe or FakeProbe()
    supervisor = ModelSupervisor(
        contract_roster(), children, health, stop_grace_s=_TINY, reap_timeout_s=_TINY
    )
    return supervisor, children, health


def test_the_roster_is_what_the_daemon_serves_and_nothing_else() -> None:
    supervisor, _, _ = _supervisor()
    assert supervisor.models == (CORTEX, DEEP)


@pytest.mark.parametrize("verb", ["start", "stop", "status"])
async def test_every_verb_refuses_an_id_the_roster_does_not_hold(verb: str) -> None:
    """A request cannot name a model into existence: that is the whole safety of the control API."""
    supervisor, processes, _ = _supervisor()
    with pytest.raises(UnknownModelError, match="unknown model 'ghost'"):
        await getattr(supervisor, verb)("ghost")
    assert processes.spawned == []


async def test_a_start_spawns_the_specs_argv_once_however_often_it_is_asked() -> None:
    """Idempotence is a single process, not a tolerated second one holding the same port."""
    supervisor, processes, _ = _supervisor()
    await supervisor.start(CORTEX)
    await supervisor.start(CORTEX)
    await supervisor.start(CORTEX)
    assert len(processes.spawned) == 1
    assert processes.spawned[0].argv == contract_roster()[CORTEX].argv


async def test_two_concurrent_starts_spawn_one_process() -> None:
    """A stop racing a start is what produces a bind failure, so the three verbs serialize.

    The fake suspends inside ``spawn``, so the first start genuinely holds the per-model lock
    while the second arrives: without the lock both would see no child and both would spawn.
    """
    supervisor, processes, _ = _supervisor()
    processes.gate = asyncio.Event()
    first = asyncio.create_task(supervisor.start(CORTEX))
    second = asyncio.create_task(supervisor.start(CORTEX))
    await asyncio.sleep(0)
    processes.gate.set()
    await asyncio.gather(first, second)
    assert len(processes.spawned) == 1


async def test_a_spawn_that_fails_starts_nothing_and_raises_a_typed_error() -> None:
    """A failed start must leave the model absent, or a swap would health-gate a phantom."""
    supervisor, processes, _ = _supervisor()
    processes.error = OSError("no such file or directory")
    with pytest.raises(SupervisorError, match="could not start 'cortex'"):
        await supervisor.start(CORTEX)
    status = await supervisor.status(CORTEX)
    assert status == ModelStatus(CORTEX, ModelHostState.STOPPED, "no process is running")


async def test_a_spawn_that_fails_over_a_dead_child_keeps_reporting_that_childs_exit_code() -> None:
    """A failed replacement does not erase the corpse: this tier's last process really did die.

    The spawn failure itself is what the ``start`` answers with (a 503 carrying the OS error), so
    nothing is hidden by leaving the slot alone. What ``status`` then reports is the exit code of
    the process that actually ran, which is what the runbook reads; STOPPED would say "nothing has
    ever happened to this tier" about a tier whose model crashed. The next successful start
    replaces it, which is the case the shared contract covers.
    """
    supervisor, processes, _ = _supervisor()
    await supervisor.start(CORTEX)
    processes.spawned[0].exit(7)
    processes.error = OSError("no such file or directory")
    with pytest.raises(SupervisorError, match="could not start 'cortex'"):
        await supervisor.start(CORTEX)
    assert await supervisor.status(CORTEX) == ModelStatus(
        CORTEX, ModelHostState.FAILED, "the process exited with code 7"
    )


async def test_status_reads_the_exit_code_without_asking_the_probe_at_all() -> None:
    """The probe is never consulted for a dead child: the witness is that it was not called.

    Measured hazard: a start that could not bind dies at once while the model it was replacing
    keeps answering 200 on that port. Asking would get the wrong answer, so it is not asked.
    """
    supervisor, processes, probe = _supervisor()
    roster = contract_roster()
    probe.set(roster[DEEP].health_url, serving=True)
    await supervisor.start(DEEP)
    processes.last_for(roster[DEEP].port).exit(1)
    probe.probed.clear()
    status = await supervisor.status(DEEP)
    assert status == ModelStatus(DEEP, ModelHostState.FAILED, "the process exited with code 1")
    assert probe.probed == []


async def test_status_reports_the_loading_pid_of_a_child_that_is_not_serving_yet() -> None:
    supervisor, processes, _ = _supervisor()
    await supervisor.start(DEEP)
    pid = processes.spawned[0].pid
    assert await supervisor.status(DEEP) == ModelStatus(
        DEEP, ModelHostState.LOADING, f"pid {pid} is not serving yet"
    )


async def test_stop_does_not_return_until_the_child_is_reaped() -> None:
    """``swap_in`` starts the next model immediately after this returns, so VRAM must be free.

    The child here honours no signal until the test lets it exit, which is how the ordering is
    observed rather than assumed: the stop is still pending while the process is alive.
    """
    supervisor, processes, _ = _supervisor(FakeChildProcesses(exits_on=None))
    await supervisor.start(CORTEX)
    child = processes.spawned[0]
    supervisor_stop = asyncio.create_task(supervisor.stop(CORTEX))
    await asyncio.sleep(0)
    assert not supervisor_stop.done()
    assert child.returncode is None
    child.exit(0)
    await supervisor_stop
    assert child.signals == ["terminate"]
    assert (await supervisor.status(CORTEX)).state is ModelHostState.STOPPED


async def test_a_wedged_child_is_killed_after_the_grace() -> None:
    """SIGTERM first, SIGKILL after the bound, and the stop completes either way."""
    supervisor, processes, _ = _supervisor(FakeChildProcesses(exits_on="kill"))
    await supervisor.start(CORTEX)
    await supervisor.stop(CORTEX)
    child = processes.spawned[0]
    assert child.signals == ["terminate", "kill"]
    assert child.returncode == -9
    assert await supervisor.status(CORTEX) == ModelStatus(
        CORTEX, ModelHostState.STOPPED, "no process is running"
    )


async def test_a_child_that_survives_sigkill_keeps_being_reported() -> None:
    """The one stop that can fail: a process still holding VRAM must not vanish into STOPPED.

    The caller retries (``restore_standing`` does, once), and a slot reported STOPPED would have
    told the swap the GPU was free when it is not.
    """
    supervisor, processes, probe = _supervisor(FakeChildProcesses(exits_on=None))
    roster = contract_roster()
    probe.set(roster[CORTEX].health_url, serving=True)
    await supervisor.start(CORTEX)
    with pytest.raises(SupervisorError, match="survived SIGKILL"):
        await supervisor.stop(CORTEX)
    assert processes.spawned[0].signals == ["terminate", "kill"]
    # Still reported as the running process it is, on the probe's own answer: the slot was NOT
    # released, which is the point. A deleted slot would read STOPPED here.
    assert (await supervisor.status(CORTEX)).state is ModelHostState.READY


async def test_stop_all_stops_every_model_and_survives_one_that_will_not_die() -> None:
    """A shutdown that raised on the first wedged child would leave the rest holding the GPU."""
    supervisor, processes, _ = _supervisor(FakeChildProcesses(exits_on=None))
    await supervisor.start(CORTEX)
    await supervisor.start(DEEP)
    processes.spawned[1].exit(0)  # the deep model dies politely; the cortex is wedged
    await supervisor.stop_all()
    assert [child.signals for child in processes.spawned] == [["terminate", "kill"], []]
    assert (await supervisor.status(DEEP)).state is ModelHostState.STOPPED
    assert (await supervisor.status(CORTEX)).state is ModelHostState.LOADING
