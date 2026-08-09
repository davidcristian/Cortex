"""The model-host contract: the scriptable twin, the readiness gate, and the two sleepers.

Everything a swap knows about a model process goes through these three: what the host reports
(``ScriptedModelHost``), how long the swap waits for READY (``await_model_ready``), and how it
waits at all (the ``Sleeper`` port). Every wait here is either an already-expired bound or a
recorded one, so no test sleeps wall-clock; ``RecordingSleeper`` yields the loop instead, which
is scheduling, not time.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- returning READY unconditionally from the gate's timeout branch reddens
  ``test_the_gate_reports_the_last_state_when_the_bound_elapses``;
- computing the gate's deadline inside the poll loop reddens
  ``test_the_gate_gives_up_once_the_clock_passes_the_bound_it_took_at_the_start`` (against a
  clock that advances, the recomputed deadline is never reached, so the gate never gives up);
  the already-expired-bound test alone does NOT discriminate that mutation, which is why the
  ticking-clock test exists;
- dropping the ``fail_once`` pop (making it permanent) reddens
  ``test_a_scripted_failure_can_be_armed_for_one_call_only``;
- applying the fake's effect after its pause rather than before reddens
  ``test_a_paused_operation_has_already_taken_effect_when_it_blocks``.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    DEFAULT_HEALTH_POLL_INTERVAL_S,
    DEFAULT_SWAP_DRAIN_TIMEOUT_S,
    DEFAULT_SWAP_LOAD_TIMEOUT_S,
    AsyncioSleeper,
    Clock,
    ControlBounds,
    DeviceMemory,
    ModelHost,
    ModelHostError,
    ModelHostState,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    Sleeper,
    await_model_ready,
)

_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


class _FixedClock:
    """A clock that never advances: a bound is reached only because it was already expired."""

    def now(self) -> datetime:
        return _AT


class _TickingClock:
    """A clock that advances one second per reading, deterministically, without any waiting."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


class _LoadingThenReady:
    """A host whose model finishes loading after ``polls`` probes (the real gate's whole point)."""

    def __init__(self, polls: int) -> None:
        self.polls = polls
        self.probes = 0

    async def start(self, model: str) -> None:
        del model

    async def stop(self, model: str) -> None:
        del model

    async def status(self, model: str) -> ModelHostState:
        del model
        self.probes += 1
        if self.probes <= self.polls:
            return ModelHostState.LOADING
        return ModelHostState.READY

    async def device_memory(self) -> DeviceMemory | None:
        return None

    async def control_bounds(self) -> ControlBounds | None:
        return None

    async def boot_id(self) -> str | None:
        return None


def test_the_plan_rejects_bounds_that_could_not_govern_a_swap() -> None:
    """Bounds a swap could not be governed by are boot-time misconfigurations, not surprises."""
    with pytest.raises(ValueError, match="drain_timeout_s must be >= 0"):
        _plan(drain_timeout_s=-1.0)
    with pytest.raises(ValueError, match="load_timeout_s must be >= 0"):
        _plan(load_timeout_s=-1.0)
    with pytest.raises(ValueError, match="poll_interval_s must be > 0"):
        _plan(poll_interval_s=0.0)
    with pytest.raises(ValueError, match="brain_vram_mib must be >= 0"):
        _plan(brain_vram_mib=-1)
    with pytest.raises(ValueError, match="brain_decode_tps must be >= 0"):
        _plan(brain_decode_tps=-1.0)
    with pytest.raises(ValueError, match="control_deadline_s must be >= 0"):
        _plan(control_deadline_s=-1.0)


def test_the_plan_defaults_its_bounds_to_the_documented_values() -> None:
    """The deployment overrides both; the defaults are what a stock stack swaps under."""
    plan = _plan(evict_models=("subagent-gpu",))
    assert plan.evict_models == ("subagent-gpu",)
    assert (plan.load_timeout_s, ResidencyPlan("c", "b").load_timeout_s) == (
        60.0,
        DEFAULT_SWAP_LOAD_TIMEOUT_S,
    )
    assert ResidencyPlan("c", "b").poll_interval_s == DEFAULT_HEALTH_POLL_INTERVAL_S
    assert ResidencyPlan("c", "b").drain_timeout_s == DEFAULT_SWAP_DRAIN_TIMEOUT_S
    # Co-residency is the deployment's own assertion about its card, so a plan that was not
    # told holds the shipped rule: the deep model runs alone.
    assert ResidencyPlan("c", "b").coresident is False
    assert _plan(coresident=True).coresident is True
    # A deployment that never measured its deep tier's rate judges no handoff by it.
    assert ResidencyPlan("c", "b").brain_decode_tps == 0.0
    assert _plan(brain_decode_tps=25.07).brain_decode_tps == 25.07
    # And one that bounds no control call has stated no pairing rule for a swap to re-check.
    assert ResidencyPlan("c", "b").control_deadline_s == 0.0
    assert _plan(control_deadline_s=60.0).control_deadline_s == 60.0


def test_the_control_bounds_sum_every_term_one_stop_can_spend() -> None:
    """All three, because a two-term reading of this rule is what shipped the pairing wrong.

    The shipped numbers, and their sum is the figure the runbook writes out: a stop can pay a
    queued status's probe deadline before it starts, then the SIGTERM grace, then the reap.
    """
    assert ControlBounds(5.0, 10.0, 30.0).worst_case_stop_s == 45.0


def test_a_deadline_only_clears_the_worst_case_when_it_sits_strictly_above_it() -> None:
    """The boundary is the whole point: equal is a timeout on the very call the sum describes.

    The pair below is the tuning the ADR measured somebody reaching by the two-term rule (20 and
    35 look like a compliant 55), which the probe timeout carries to exactly the 60 s deadline.
    """
    bounds = ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)
    assert bounds.clears(61.0) is True
    assert bounds.clears(60.0) is False
    assert bounds.clears(45.0) is False
    assert ControlBounds(5.0, 10.0, 30.0).clears(60.0) is True


async def test_the_scripted_host_reports_the_bounds_it_was_given_and_none_by_default() -> None:
    """A twin whose ``stop`` is a set removal has no grace and no reap, so it claims none.

    The composition root's pairing check reads exactly this, and ``None`` is what tells it there
    is nothing to compare rather than a sum it could act on.
    """
    assert await ScriptedModelHost().control_bounds() is None
    wired = ControlBounds(probe_timeout_s=1.0, stop_grace_s=2.0, reap_timeout_s=3.0)
    assert await ScriptedModelHost(control_bounds=wired).control_bounds() == wired


async def test_the_bounds_read_can_be_scripted_to_fail_like_any_other_call() -> None:
    """It reaches a real sidecar over HTTP, so an unreachable host has to be arrangeable."""
    host = ScriptedModelHost(fail={("control_bounds", ""): "the supervisor is not there"})
    with pytest.raises(ModelHostError, match="not there"):
        await host.control_bounds()
    assert host.calls == [("control_bounds", "")]


async def test_the_scripted_host_starts_stops_and_reports_idempotently() -> None:
    """The port's contract: both verbs are idempotent and readiness is only ever observed."""
    host: ModelHost = ScriptedModelHost(running=["cortex"])
    assert await host.status("cortex") is ModelHostState.READY
    assert await host.status("brain") is ModelHostState.STOPPED
    await host.start("brain")
    await host.start("brain")  # idempotent: starting a started model changes nothing
    assert await host.status("brain") is ModelHostState.READY
    await host.stop("brain")
    await host.stop("brain")  # idempotent the same way
    assert await host.status("brain") is ModelHostState.STOPPED


async def test_the_scripted_host_reports_an_overridden_state_for_a_running_model() -> None:
    """How a model that dies at load, or never finishes one, is scripted."""
    host = ScriptedModelHost(
        running=["brain", "cortex"],
        status_override={"brain": ModelHostState.FAILED, "cortex": ModelHostState.LOADING},
    )
    assert await host.status("brain") is ModelHostState.FAILED
    assert await host.status("cortex") is ModelHostState.LOADING
    await host.stop("brain")
    # A stopped model reports STOPPED whatever its override said: it is not running at all.
    assert await host.status("brain") is ModelHostState.STOPPED


async def test_a_scripted_failure_is_typed_and_logged_in_the_call_order() -> None:
    """Failures cross the port as ModelHostError, and the op log still records the attempt."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "no VRAM"})
    with pytest.raises(ModelHostError, match="no VRAM"):
        await host.start("brain")
    assert host.calls == [("start", "brain")]
    assert "brain" not in host.running  # a failed start started nothing


async def test_a_scripted_failure_can_be_armed_for_one_call_only() -> None:
    """The restore's retry needs exactly this: fail the first attempt, succeed the second."""
    host = ScriptedModelHost(fail_once={("start", "cortex"): "device busy"})
    with pytest.raises(ModelHostError, match="device busy"):
        await host.start("cortex")
    await host.start("cortex")
    assert host.running == {"cortex"}


async def test_a_paused_operation_has_already_taken_effect_when_it_blocks() -> None:
    """A kill at a boundary is the analogue of a death AFTER the effect, so the effect lands."""
    host = ScriptedModelHost(running=["cortex"], pause_at=[("stop", "cortex")])
    task = asyncio.create_task(host.stop("cortex"))
    async with asyncio.timeout(5.0):
        await host.reached[("stop", "cortex")].wait()
    assert host.running == set()  # the cortex is genuinely down while the world is paused
    assert not task.done()
    host.release[("stop", "cortex")].set()
    await task


async def test_the_gate_returns_ready_as_soon_as_the_model_serves() -> None:
    sleeper = RecordingSleeper()
    host = ScriptedModelHost(running=["brain"])
    state = await await_model_ready(
        host, "brain", clock=_FixedClock(), sleeper=sleeper, plan=_plan()
    )
    assert state is ModelHostState.READY
    assert sleeper.waits == []  # a model already serving is never waited on


async def test_the_gate_polls_between_waits_until_the_load_finishes() -> None:
    """The poll loop: one recorded wait per unsettled probe, at the plan's interval."""
    sleeper = RecordingSleeper()
    host = _LoadingThenReady(polls=3)
    plan = _plan(poll_interval_s=0.25)
    state = await await_model_ready(host, "brain", clock=_FixedClock(), sleeper=sleeper, plan=plan)
    assert state is ModelHostState.READY
    assert (host.probes, sleeper.waits) == (4, [0.25, 0.25, 0.25])


async def test_the_gate_returns_failed_at_once_without_waiting_out_the_bound() -> None:
    """A model that died at load is settled: there is nothing left to wait for."""
    sleeper = RecordingSleeper()
    host = ScriptedModelHost(running=["brain"], status_override={"brain": ModelHostState.FAILED})
    state = await await_model_ready(
        host, "brain", clock=_FixedClock(), sleeper=sleeper, plan=_plan()
    )
    assert (state, sleeper.waits) == (ModelHostState.FAILED, [])


async def test_the_gate_reports_the_last_state_when_the_bound_elapses() -> None:
    """An already-expired bound ends the gate on the first unsettled probe, telling which."""
    sleeper = RecordingSleeper()
    expired = _plan(load_timeout_s=0.0)
    loading = ScriptedModelHost(
        running=["brain"], status_override={"brain": ModelHostState.LOADING}
    )
    assert (
        await await_model_ready(
            loading, "brain", clock=_FixedClock(), sleeper=sleeper, plan=expired
        )
        is ModelHostState.LOADING
    )
    never_started = ScriptedModelHost()
    assert (
        await await_model_ready(
            never_started, "brain", clock=_FixedClock(), sleeper=sleeper, plan=expired
        )
        is ModelHostState.STOPPED
    )
    assert sleeper.waits == []  # the bound was already expired, so nothing was waited on


async def test_the_gate_gives_up_once_the_clock_passes_the_bound_it_took_at_the_start() -> None:
    """The bound must be taken ONCE, before the first poll, or it bounds nothing.

    Read against a clock that advances a second per reading (as a real one does): a gate whose
    deadline is recomputed each round would poll a stuck load forever.
    """
    sleeper = RecordingSleeper()
    host = ScriptedModelHost(running=["brain"], status_override={"brain": ModelHostState.LOADING})
    async with asyncio.timeout(5.0):
        state = await await_model_ready(
            host,
            "brain",
            clock=_TickingClock(),
            sleeper=sleeper,
            plan=_plan(load_timeout_s=3.0),
        )
    assert state is ModelHostState.LOADING
    assert 0 < len(sleeper.waits) <= 4  # bounded by the clock, not by the host settling


async def test_a_dead_host_surfaces_from_the_gate_rather_than_being_guessed_at() -> None:
    host = ScriptedModelHost(running=["brain"], fail={("status", "brain"): "supervisor gone"})
    with pytest.raises(ModelHostError, match="supervisor gone"):
        await await_model_ready(
            host, "brain", clock=_FixedClock(), sleeper=RecordingSleeper(), plan=_plan()
        )


async def test_the_recording_sleeper_yields_the_loop_instead_of_consuming_time() -> None:
    """The twin's contract: the schedule is observable and other tasks still get to run."""
    sleeper: Sleeper = RecordingSleeper()
    ran = False

    async def other() -> None:
        nonlocal ran
        ran = True

    task = asyncio.create_task(other())
    await sleeper.sleep(300.0)
    assert ran is True  # a 300 s wait cost the test nothing but one loop turn
    await task
    assert isinstance(sleeper, RecordingSleeper)
    assert sleeper.waits == [300.0]


async def test_the_real_sleeper_suspends_the_caller_and_resumes() -> None:
    """AsyncioSleeper is production wiring, so it is exercised: a zero wait still yields."""
    sleeper: Sleeper = AsyncioSleeper()
    ran = False

    async def other() -> None:
        nonlocal ran
        ran = True

    task = asyncio.create_task(other())
    await sleeper.sleep(0)
    assert ran is True
    await task


def test_the_clock_port_is_what_bounds_the_gate() -> None:
    """The bound is measured on the injected Clock, never on a real deadline."""
    clock: Clock = _FixedClock()
    assert clock.now() == _AT
