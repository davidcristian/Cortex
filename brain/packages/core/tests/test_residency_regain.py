"""Regaining residency without a turn: the state a restore that gave up used to leave for ever.

The unit under test is the whole path the ADR-0030 residency-regain addendum describes, driven
through the real ``SwappingModelManager`` over the scripted host, because the defect is an
interaction rather than a function: a swap back that gave up publishes that nothing is resident,
every ``acquire`` is then refused, so no turn runs, so no handoff starts, so the reconciliation a
handoff would have run is unreachable exactly when it is the thing that is needed. Every case here
therefore asserts what a probe reads **and** what a lease does, before and after a pass.

The headline case is the runbook's own manual recovery with its last step removed: the operator
starts the cortex through the sidecar's control API, and the brain notices by itself instead of
being restarted.

Distrust-green proofs (each mutation applied to production code alone, the whole brain workspace
re-run, then reverted, so the counts are measured rather than aimed at):
- publishing on the cortex's own state alone, dropping the deep-tier reading, reddens 6: both arms
  of ``test_a_deep_model_still_on_the_card_stops_the_regain``, which is the guard against handing
  a lease out onto a card that already holds another tier, plus the four cases that read the
  second status call out of the host's op log;
- treating a host that could not be asked as evidence the cortex is serving reddens 1,
  ``test_a_host_that_cannot_be_asked_about_the_cortex_publishes_nothing``;
- treating an unanswerable deep tier the same way reddens 1,
  ``test_a_host_that_cannot_be_asked_about_the_deep_model_publishes_nothing``;
- publishing without testing the fence at all reddens 1,
  ``test_a_handoff_that_begins_mid_pass_wins_the_publish``. What that pins is that the fence is
  consulted at the write and not only at the top of the pass; the tighter property, that the
  answer and the write are under one condition with nothing awaited between them, has no mutation
  that can show it, because inserting an await there lets a claim run and a claim takes the same
  condition, so it blocks rather than interleaves. The argument for it is in the ADR;
- regaining without the standing charge reddens 1,
  ``test_a_regained_residency_charges_the_placer_for_the_cortex_again``;
- reading the machine even while the report says serving reddens 7,
  ``test_a_serving_report_costs_the_pass_no_control_call_at_all`` plus six cases in
  ``test_residency_tiers.py`` that pin a whole pass's op log, which is what keeps a healthy
  deployment paying nothing new;
- regaining before the sweep rather than after it reddens 1,
  ``test_a_pass_sweeps_the_peers_before_it_republishes_the_resident``;
- dropping the regain from the pass altogether reddens 12: every case here but
  ``test_a_serving_report_costs_the_pass_no_control_call_at_all``, which asserts an empty op log
  either way, plus the composition root's
  ``test_a_cortex_that_comes_up_after_the_boot_verdict_turns_the_seam_green``, the only case
  anywhere that drives the healer's own loop rather than one pass.
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_LOST,
    RESIDENCY_SERVING,
    TIERS_MISSING_DETAIL,
    DeviceMemory,
    ModelHostState,
    ModelUnavailableError,
    PlacementRequest,
    PlacementTarget,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyRestoreError,
    ScriptedModelHost,
    SwappingModelManager,
    VramBudgetPlacer,
)

_CORTEX = "cortex"
_DEEP = "brain"
_TIER = "subagent-gpu"
_ENDPOINTS = {_CORTEX: "http://llama-cortex:8080", _DEEP: "http://llama-brain:8081"}
_REGAIN_LOGGER = "cortex_core.residency_regain"
_REGAINED = "the cortex is serving again, so residency was regained without a restart"
_NO_CORTEX_READING = (
    "the model host could not be asked whether the cortex is serving again: error=%s"
)
_NO_DEEP_READING = (
    "the model host could not be asked whether the deep model is still resident: error=%s"
)


class _FixedClock:
    """A clock that never advances; every gate here settles on a state or on an expired bound."""

    def now(self) -> datetime:
        return datetime(2026, 8, 18, 21, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": _CORTEX,
        "brain_model": _DEEP,
        "evict_models": (),
        "load_timeout_s": 0.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _manager(
    host: ScriptedModelHost,
    placer: VramBudgetPlacer | None = None,
    plan: ResidencyPlan | None = None,
) -> SwappingModelManager:
    return SwappingModelManager(
        host,
        _ENDPOINTS,
        plan if plan is not None else _plan(),
        _FixedClock(),
        RecordingSleeper(),
        placer,
    )


def _stalled_host(**overrides: object) -> ScriptedModelHost:
    """A host whose cortex starts and then never serves, which is what makes a restore give up."""
    fields: dict[str, object] = {
        "running": [_CORTEX],
        "status_override": {_CORTEX: ModelHostState.FAILED},
    }
    return ScriptedModelHost(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _regain_log(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Only this module's own lines: every case here first drove a swap that logged its failure."""
    return [record.msg for record in caplog.records if record.name == _REGAIN_LOGGER]


async def _give_up(manager: SwappingModelManager) -> None:
    """Run one handoff whose swap back fails twice, which is the state this module exists for."""
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope(_DEEP):
            pass  # pragma: no cover -- a failed swap in never runs the scope's body
    assert manager.residency() == RESIDENCY_LOST


async def _refuses_every_turn(manager: SwappingModelManager) -> None:
    """The cost of the dead end, asserted rather than described: no turn can run at all."""
    with pytest.raises(ModelUnavailableError, match="resident: None"):
        async with manager.acquire(_CORTEX):
            pass  # pragma: no cover -- the acquire raises before the body runs


async def _serves_turns_again(manager: SwappingModelManager) -> None:
    """And the recovery, asserted the same way: the lease hands out the cortex once more."""
    async with manager.acquire(_CORTEX) as lease:
        assert lease.endpoint == _ENDPOINTS[_CORTEX]


def _placer() -> VramBudgetPlacer:
    """Headroom 3.0 GiB beside the cortex, so the 2.0 GiB spawn below lands on the GPU."""
    return VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)


def _spawn() -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)


async def test_a_restore_that_gave_up_is_regained_by_the_next_pass_with_no_restart(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The entry's whole point: the manual recovery no longer ends by restarting the brain.

    Nothing about the machine is touched by the pass. The operator (or the sidecar's own boot
    default after a restart) put the cortex back through the control API, and all the brain owes
    is a reading of it.
    """
    host = _stalled_host()
    manager = _manager(host)
    await _give_up(manager)
    await _refuses_every_turn(manager)
    host.set_status(_CORTEX, None)  # POST /models/cortex/start, and it came up this time
    host.calls.clear()
    with caplog.at_level(logging.INFO, logger=_REGAIN_LOGGER):
        await manager.heal_residency()
    assert host.calls == [("status", _CORTEX), ("status", _DEEP)]  # read, never written
    assert manager.residency() == RESIDENCY_SERVING
    await _serves_turns_again(manager)
    assert _regain_log(caplog) == [_REGAINED]


async def test_a_serving_report_costs_the_pass_no_control_call_at_all() -> None:
    """The common case is a healthy deployment, so it must pay nothing for this to exist."""
    host = ScriptedModelHost(running=[_CORTEX])
    manager = _manager(host)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == []
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_cortex_that_is_not_serving_yet_leaves_the_report_where_it_was() -> None:
    """A pass while the machine is still broken is one status call and no verdict at all.

    The deep tier is not even asked about, nothing it could be doing making a cortex that is not
    serving into a standing residency.
    """
    host = _stalled_host()
    manager = _manager(host)
    await _give_up(manager)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _CORTEX)]
    assert manager.residency() == RESIDENCY_LOST
    await _refuses_every_turn(manager)


@pytest.mark.parametrize("deep_state", [ModelHostState.READY, ModelHostState.LOADING])
async def test_a_deep_model_still_on_the_card_stops_the_regain(
    deep_state: ModelHostState,
) -> None:
    """A restore can give up at the stop as easily as at the start, and then both tiers are up.

    This is the runbook's own warning as a guard. An operator who starts the cortex while the deep
    tier is still resident has put two models on one card, and a brain that published serving
    there would hand leases out onto it. ``LOADING`` counts as on the card exactly as ``READY``
    does, the weights being allocated either way; both arms are reached the same way, by a stop
    the host refuses, which is what leaves the deep tier up after the restore has run twice.
    """
    host = _stalled_host(
        status_override={_CORTEX: ModelHostState.FAILED, _DEEP: deep_state},
        fail={("stop", _DEEP): "still resident"},
    )
    manager = _manager(host)
    await _give_up(manager)
    host.running.add(_CORTEX)  # started by hand, against the runbook's advice
    host.set_status(_CORTEX, None)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _CORTEX), ("status", _DEEP)]
    assert manager.residency() == RESIDENCY_LOST
    await _refuses_every_turn(manager)


async def test_a_deep_tier_the_daemon_never_had_is_off_the_card() -> None:
    """Nothing can be resident under a name this daemon's roster does not carry.

    It is a reachable shape rather than a theoretical one: a deployment that turned escalation on
    without naming an artifact for the deep tier fails its swap at the start, and the restore
    behind that failure is what can leave the GPU serving nothing.
    """
    host = _stalled_host(unhosted=[_DEEP])
    manager = _manager(host)
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    await manager.heal_residency()
    assert manager.residency() == RESIDENCY_SERVING
    await _serves_turns_again(manager)


async def test_a_host_that_cannot_be_asked_about_the_cortex_publishes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No reading is not a reading that says yes, which is the direction that would be worse.

    A pass that read a transport failure as a serving cortex would hand out leases onto a card it
    has no evidence about, every interval, on the one path where the evidence is the whole point.
    """
    host = ScriptedModelHost(running=[_CORTEX], fail={("status", _CORTEX): "connection refused"})
    manager = _manager(host)
    await _give_up(manager)
    host.calls.clear()
    with caplog.at_level(logging.DEBUG, logger=_REGAIN_LOGGER):
        await manager.heal_residency()
    assert host.calls == [("status", _CORTEX)]
    assert manager.residency() == RESIDENCY_LOST
    assert _regain_log(caplog) == [_NO_CORTEX_READING]


async def test_a_host_that_cannot_be_asked_about_the_deep_model_publishes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The same posture one reading later: an unanswered deep tier is not a cleared one."""
    host = _stalled_host(fail={("status", _DEEP): "connection refused"})
    manager = _manager(host)
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    with caplog.at_level(logging.DEBUG, logger=_REGAIN_LOGGER):
        await manager.heal_residency()
    assert manager.residency() == RESIDENCY_LOST
    assert _regain_log(caplog) == [_NO_DEEP_READING]


async def test_a_handoff_that_begins_mid_pass_wins_the_publish() -> None:
    """The race the guarded publish exists for, run rather than reasoned about.

    A pass reads the machine over several awaits, so a handoff can be claimed between what it
    observed and what it concludes. The publish tests the fence under the residency condition,
    with nothing awaited in between, so a reading taken before the handoff cannot overwrite the
    swap's own report. It is a race lost and not a rule, which is what the second pass shows.
    """
    host = ScriptedModelHost(running=[_CORTEX], pause_at=[("status", _DEEP)])
    manager = _manager(host)
    await manager.publish_boot_residency(serving=False)
    reached, release = host.reached[("status", _DEEP)], host.release[("status", _DEEP)]
    first = asyncio.create_task(manager.heal_residency())
    async with asyncio.timeout(5.0):
        await reached.wait()
        async with manager.handoff_claim():
            release.set()
            await first
            assert manager.residency() == RESIDENCY_BOOT_FAILED
        await manager.heal_residency()
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_pass_sweeps_the_peers_before_it_republishes_the_resident() -> None:
    """One pass, one reading of one machine, in the order a probe has to read it back.

    The peers are refreshed first, so the report the regain publishes is composed over a record
    this same pass has just written: the cortex is serving again and the tier the handoff evicted
    has been asked back but not yet observed serving, which is exactly what the seam says.
    """
    host = _stalled_host()
    manager = _manager(host, plan=_plan(evict_models=(_TIER,)))
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [
        ("status", _TIER),
        ("start", _TIER),
        ("status", _CORTEX),
        ("status", _DEEP),
    ]
    report = manager.residency()
    assert report.serving is True
    assert report.detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    await manager.heal_residency()  # the tier is observed serving; the resident half stands down
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_regained_residency_charges_the_placer_for_the_cortex_again() -> None:
    """The other half of the dead end: delegation stayed on the CPU until the process restarted.

    A restore that gave up leaves the handoff's VRAM charge standing on purpose, because nobody
    can describe the card any more. The reading that describes it again is what spends that
    reason, and it lands with the publish rather than a pass later.
    """
    placer = _placer()
    host = _stalled_host(device_memory=DeviceMemory(free_mib=20000, total_mib=24000))
    manager = _manager(host, placer, _plan(brain_vram_mib=13312))
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    await _give_up(manager)
    assert placer.place(_spawn()).target is PlacementTarget.CPU  # the deep model holds the card
    host.set_status(_CORTEX, None)
    await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_boot_that_could_not_confirm_the_cortex_goes_green_when_it_comes_up() -> None:
    """The cheap half of the same hole: an amber dot nothing but a restart could ever clear.

    The lease was forgiving throughout, deliberately, so what changes here is only what a human is
    told. Before this pass existed that sentence stood until the next handoff, and a deployment
    that never escalates has no next handoff.
    """
    host = ScriptedModelHost(running=[_CORTEX])
    manager = _manager(host)
    await manager.publish_boot_residency(serving=False)
    assert manager.residency() == RESIDENCY_BOOT_FAILED
    await _serves_turns_again(manager)  # amber, and still leasable: the boot publish is display
    await manager.heal_residency()
    assert manager.residency() == RESIDENCY_SERVING
