"""A peer of the standing residency that is not serving: the record, the placer, and the sweep.

The unit under test is the whole path the ADR-0030 tier-outage and tier-sweep addenda describe,
because no part of it is worth anything alone: a record nothing reads is a dict, a closed placer
nothing writes is a dead branch, and a pass with nothing to act on never runs. So the cases here
drive the real ``SwappingModelManager`` over the scripted host with a real ``VramBudgetPlacer``,
and ask where a spawn would land and what a probe would read at each point.

The distinction every case is really about: a tier stopped **on purpose** while the deep model
holds the card is not a tier that is **down**, and only the second one closes the GPU or reaches
the seam. ``test_an_evicted_tier_is_not_a_missing_one`` is that sentence as an assertion, and
what keeps it true is now the fence rather than "only a refusal marks": a pass does not run while
a handoff owns the GPU, so an eviction is never what a reading sees.

Four of the cases below are the shapes a record written by refusals alone could not see, each one
measured escaping the code as it stood, against a real supervisor over HTTP, before it was written
here: a peer that accepted its start and then died, one that died between handoffs, one nothing
ever started because a convergence returned before its restart loop, and one whose boot could not
reach the host at all. Every one of them asserts a spawn on the GPU before the pass and on the CPU
after it, because a sweep whose test never saw the dead endpoint proves nothing.

Distrust-green proofs (each mutation applied to production code alone, the whole brain workspace
re-run, then reverted, so the counts are measured rather than aimed at):
- dropping ``tiers.mark_missing`` from ``residency_moves.restart_evicted`` reddens 7, six here
  (every case that asks where a spawn lands or what a probe reads after a failed restart) plus
  ``test_health_stays_ready_and_names_a_peer_tier_that_did_not_come_back`` at the seam;
- dropping ``tiers.mark_standing`` from the same loop's ``else`` reddens 1,
  ``test_a_second_handoff_that_restarts_the_peer_reopens_the_gpu``;
- reopening on any ``mark_standing`` rather than on an emptied record reddens 1,
  ``test_one_peer_back_of_two_keeps_the_gpu_closed``;
- annotating a not-serving report in ``StandingTiers.note_on`` reddens 1,
  ``test_an_evicted_tier_is_not_a_missing_one``, which is the down-versus-evicted rule itself;
- consulting the headroom before the closed flag in ``VramBudgetPlacer.place`` reddens 7, five
  here and two in test_placer.py;
- starting a tier that reports ``LOADING`` reddens 1,
  ``test_a_sweep_leaves_a_tier_that_is_still_loading_alone``;
- dropping the scope guard from the fence reddens 1,
  ``test_a_sweep_defers_while_a_handoff_owns_the_gpu``;
- dropping the claim guard from the fence reddens 2,
  ``test_a_sweep_defers_while_a_handoff_is_claimed_and_the_pool_is_draining`` plus
  ``test_a_handoff_that_begins_mid_pass_wins_the_publish`` in ``test_residency_regain.py``
  (re-measured 2026-08-18, when the resident half joined the pass and began reading the same
  fence at its own write);
- dropping the pass guard in ``TierHealer.run`` reddens 1,
  ``test_a_failing_pass_costs_one_pass_and_not_the_loop``, on its own bound rather than by
  hanging, which is why every wait in this file is inside an ``asyncio.timeout``.

The tier-sweep pass measured eight more the same way, and they are the table this file's own
design rests on:
- sweeping only the tiers already believed missing reddens 10, which is the defect itself and
  every case written against it;
- letting a host that could not be asked mark the tier anyway reddens 1,
  ``test_a_sweep_that_cannot_reach_the_host_leaves_the_record_alone``, and it is the direction
  that would be worse than the defect (one blip closing GPU placement for a pool that is fine);
- going on retrying a tier the roster never had reddens 1;
- reading an unrostered restart as an ordinary refusal reddens 1, which is the ``TierFault`` the
  swap back's own loop has to write for the sweep to be able to retire it;
- marking only when the pass may also start reddens 1, the fenced pass that still owes the placer
  its reading;
- dropping the mark the reading earned reddens 7 (6 when this table was measured; the regain's
  ordering case reads the same mark through the seam);
- dropping the claim half of the fence reddens 2 (1 when this table was measured; the regain's
  own race case joined it on 2026-08-18) and dropping the scope half reddens 1, which is
  why the fence is the disjunction rather than either flag.

One case here was vacuous when it was written and the mutation table is what found it:
``test_a_peer_that_would_not_restart_closes_gpu_placement`` held its first placement's 2.0 GiB
against a 3.0 GiB headroom, so the spawn it asserted on spilled for want of room whatever the
record said, and dropping ``mark_missing`` left it green. It releases now.
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    RESIDENCY_DEEP,
    RESIDENCY_SERVING,
    TIERS_MISSING_DETAIL,
    ModelHostState,
    PlacementRequest,
    PlacementTarget,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    StandingTiers,
    SwappingModelManager,
    TierFault,
    TierHealer,
    VramBudgetPlacer,
    converge_residency,
    sweep_tiers,
)

_ENDPOINTS = {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"}
_TIER = "subagent-gpu"
_OTHER_TIER = "subagent-gpu-2"
_GHOST = "tier-with-no-artifact"
_RETRY_LOGGER = "cortex_core.residency_sweep"
_LOOP_NAME = "residency-tier-healer"


def _open() -> bool:
    """A fence that never closes, for the cases driving one pass rather than the manager."""
    return True


def _retry_log(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Only the sweep's own lines: a case that swapped first also captured the swap's failure."""
    return [record.msg for record in caplog.records if record.name == _RETRY_LOGGER]


class _FixedClock:
    """A clock that never advances; nothing here waits on one."""

    def now(self) -> datetime:
        return datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "evict_models": (_TIER,),
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _placer() -> VramBudgetPlacer:
    """Headroom 3.0 GiB beside the cortex, so the 2.0 GiB spawn below lands on the GPU."""
    return VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)


def _spawn() -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)


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


async def test_a_peer_that_would_not_restart_closes_gpu_placement() -> None:
    """The entry's whole harm: admission reopens, and the next spawn is sent to a dead server.

    The re-place on a failed GPU attempt makes that spawn survive, but it pays two loads to
    learn what the swap back already knew. Once the record exists, the placer skips the tier and
    the spawn goes to the CPU first time.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, placer)
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    # Released, or the second ask below would spill for want of headroom and prove nothing: the
    # ledger holds 2.0 of the 3.0 GiB and this file's whole point is placement that ignores it.
    placer.release(before)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_peer_that_came_back_leaves_placement_where_it_found_it() -> None:
    """The ordinary swap back: nothing is missing, so nothing is closed."""
    placer = _placer()
    manager = _manager(ScriptedModelHost(running=["cortex", _TIER]), placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert manager.residency() == RESIDENCY_SERVING


async def test_the_seam_says_which_peer_is_down_while_the_cortex_serves() -> None:
    """Legible rather than silent, on the surface that already reaches the overlay's tooltip."""
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    report = manager.residency()
    assert report.serving is True  # turns still run; this is not a swap window
    assert report.detail == TIERS_MISSING_DETAIL.format(models=_TIER)


async def test_an_evicted_tier_is_not_a_missing_one() -> None:
    """Down versus stopped on purpose, which is the distinction the whole record turns on.

    A peer is stopped for the length of every handoff, and the report already says a swap is in
    flight. Annotating that would call the swap a fault and would put two different sentences
    about the same tier on one probe.
    """
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    assert manager.residency().detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    async with manager.swap_scope("brain"):
        # The tier is stopped again here, and known missing besides. The window's own words win.
        assert manager.residency() == RESIDENCY_DEEP


async def test_a_second_handoff_that_restarts_the_peer_reopens_the_gpu() -> None:
    """A successful start is a clearing path, so a handoff that works undoes a handoff that did."""
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert manager.residency() == RESIDENCY_SERVING


async def test_one_peer_back_of_two_keeps_the_gpu_closed() -> None:
    """The placer holds one bit for the card, so the last missing tier is what reopens it."""
    placer = _placer()
    tiers = StandingTiers(placer)
    tiers.mark_missing(_TIER)
    tiers.mark_missing(_OTHER_TIER)
    tiers.mark_standing(_TIER)
    assert tiers.missing == (_OTHER_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    tiers.mark_standing(_OTHER_TIER)
    assert tiers.missing == ()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


def test_a_deployment_with_no_pool_still_records_which_peer_is_down() -> None:
    """``None`` places nothing, so the record still stands and there is nothing to close.

    Both faults, because both are reachable on such a deployment: the seam still has to name a
    tier that is down, and an operator still has to be told which of the two kinds it is.
    """
    tiers = StandingTiers()
    assert tiers.placer is None
    tiers.mark_missing(_TIER)
    assert tiers.missing == (_TIER,)
    assert tiers.note_on(RESIDENCY_SERVING).detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    tiers.mark_unhosted(_GHOST)
    assert tiers.missing == (_TIER, _GHOST)
    assert tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    tiers.mark_standing(_TIER)
    tiers.mark_standing(_GHOST)
    assert tiers.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


async def test_a_sweep_that_meets_the_fence_mid_pass_records_without_starting() -> None:
    """The fence is read again immediately before each start, so a handoff wins the race it enters.

    The record is written first and deliberately: whether or not this pass may touch the card, the
    placer must stop sending spawns at a tier the reading just found stopped.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex"])
    tiers = StandingTiers(placer)
    await sweep_tiers(host, _plan(), tiers, lambda: False)
    assert host.calls == [("status", _TIER)]  # read, never written
    assert tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_start_the_host_refuses_leaves_the_tier_recorded_and_the_pass_alive(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One tier the host will not start must not cost the others their pass."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", _TIER): "no such device"})
    tiers = StandingTiers(_placer())
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await sweep_tiers(host, _plan(evict_models=(_TIER, _OTHER_TIER)), tiers, _open)
    assert host.calls == [
        ("status", _TIER),
        ("start", _TIER),
        ("status", _OTHER_TIER),
        ("start", _OTHER_TIER),
    ]
    assert tiers.missing == (_TIER, _OTHER_TIER)
    assert "a tier of the standing residency could not be %s: model=%s error=%s" in _retry_log(
        caplog
    )


def test_marking_a_tier_standing_that_was_never_missing_changes_nothing() -> None:
    """The restart loop calls this for every peer it started, most of which were never down."""
    placer = _placer()
    tiers = StandingTiers(placer)
    tiers.mark_standing(_TIER)
    assert tiers.missing == ()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_retry_that_finds_the_tier_serving_reopens_the_gpu(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The clearing path the record owes, since the next handoff may be hours away.

    Two passes by design: the first finds the tier stopped and asks for it, the second observes
    it serving. Readiness is never gated inside a pass, so a tier that takes minutes to load
    costs the loop nothing while it does.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.calls.clear()
    await manager.heal_residency()  # finds it stopped, asks for it back
    assert host.calls == [("status", _TIER), ("start", _TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.CPU  # not yet observed serving
    with caplog.at_level(logging.INFO, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert _retry_log(caplog) == ["a tier the standing residency was missing is serving again"]


async def test_a_sweep_leaves_a_tier_that_is_still_loading_alone() -> None:
    """A load in flight is neither a failure to retry nor a tier to reopen the GPU for."""
    host = ScriptedModelHost(running=[_TIER], status_override={_TIER: ModelHostState.LOADING})
    tiers = StandingTiers(_placer())
    tiers.mark_missing(_TIER)
    await sweep_tiers(host, _plan(), tiers, _open)
    assert host.calls == [("status", _TIER)]  # asked, and deliberately not started again
    assert tiers.missing == (_TIER,)


async def test_a_sweep_that_cannot_reach_the_host_leaves_the_record_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pass never raises, and a host that cannot answer is never evidence about a tier.

    The second half is what a sweep has to get right and a marked-only retry never faced: a pass
    that reads a transport failure as a tier being down would close GPU placement for the whole
    pool on one blip, on a stack where every tier may in fact be serving.
    """
    placer = _placer()
    host = ScriptedModelHost(
        running=["cortex", _TIER],
        fail={("start", _TIER): "no such device", ("status", _TIER): "connection refused"},
    )
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert _retry_log(caplog) == [
        "a tier of the standing residency could not be %s: model=%s error=%s"
    ]
    standing = StandingTiers(_placer())
    await sweep_tiers(host, _plan(), standing, _open)
    assert standing.missing == ()  # nothing was observed, so nothing is believed


async def test_a_sweep_defers_while_a_handoff_owns_the_gpu() -> None:
    """Starting a peer while the deep model is alone on the card is the one forbidden move."""
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    async with manager.swap_scope("brain"):
        host.calls.clear()
        await manager.heal_residency()
        assert host.calls == []


async def test_a_sweep_defers_while_a_handoff_is_claimed_and_the_pool_is_draining() -> None:
    """The claim is the wider half of the fence, and it is taken before anything is evicted.

    A conductor holds it through the drain, which is up to a minute in which the scope flag says
    nothing at all. A pass that started a tier in that window would be loading a peer into the
    room the deep model is about to be fitted against.
    """
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _placer())
    async with manager.handoff_claim():
        host.calls.clear()
        await manager.heal_residency()
        assert host.calls == []
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("start", _TIER)]


async def test_a_peer_that_accepted_its_start_and_then_died_is_found_by_the_next_pass() -> None:
    """The shape measured against a real sidecar: ``200 loading``, then ``failed`` seconds later.

    The swap back marked the tier standing on the host's acceptance, which is all an accepted
    start ever proved, so nothing in the record is wrong and nothing in the record is right
    either. Only a reading of the machine can tell.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER])
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    host.set_status(_TIER, ModelHostState.FAILED)  # the child it accepted has exited
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU  # a spawn at a dead endpoint
    placer.release(before)
    await manager.heal_residency()
    assert manager.standing_tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert manager.residency().detail == TIERS_MISSING_DETAIL.format(models=_TIER)


async def test_a_peer_that_died_between_handoffs_is_found_without_any_handoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No swap, no refusal, nothing to write the record: the reading is the only witness."""
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER])
    manager = _manager(host, placer)
    host.set_status(_TIER, ModelHostState.FAILED)
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert _retry_log(caplog) == [
        "a tier of the standing residency stopped without anything asking it to: model=%s "
        "state=%s; delegated work runs on the CPU until it is serving again"
    ]


async def test_a_peer_nothing_ever_started_is_found_by_the_first_pass() -> None:
    """A convergence that returned before its restart loop asked nothing to run, so it marked none.

    Boot recovery starts every evictable peer, but only after the deep model is cleared and the
    cortex is settled, and a deep model that will not stop answers ``False`` before either. The
    tier is then stopped, unrecorded, and placed on.
    """
    placer = _placer()
    host = ScriptedModelHost(
        running=["cortex", "brain"], fail={("stop", "brain"): "still resident"}
    )
    manager = _manager(host, placer)
    settled = await converge_residency(
        host, _plan(), manager.standing_tiers, clock=_FixedClock(), sleeper=RecordingSleeper()
    )
    assert settled is False
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    await manager.heal_residency()
    assert manager.standing_tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_boot_that_could_not_reach_the_host_is_swept_when_it_answers_again() -> None:
    """Nothing was asked to run, so nothing was marked; the sidecar then comes up a minute later.

    The pass both records the tier and asks for it back, which is the whole of the recovery a
    record written by refusals could never begin: there was no refusal, only silence.
    """
    placer = _placer()
    host = ScriptedModelHost(running=[], fail_once={("status", "brain"): "connection refused"})
    manager = _manager(host, placer)
    settled = await converge_residency(
        host, _plan(), manager.standing_tiers, clock=_FixedClock(), sleeper=RecordingSleeper()
    )
    assert settled is False
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("start", _TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_tier_the_roster_never_had_is_recorded_once_and_never_asked_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fifth shape, which does not escape and is retried for ever: noise rather than harm.

    A 404 is the one answer no retry can change while that daemon runs, so it closes placement
    exactly as firmly and stops costing a control call a pass.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST])
    plan = _plan(evict_models=(_GHOST,))
    manager = _manager(host, placer, plan)
    with caplog.at_level(logging.ERROR, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.calls.clear()
    await manager.heal_residency()
    await manager.heal_residency()
    assert host.calls == []  # two whole passes that spend nothing on a fixed answer
    assert len(_retry_log(caplog)) == 1


async def test_a_restart_refused_for_a_tier_the_roster_lacks_is_not_an_ordinary_refusal() -> None:
    """The restart loop draws the same line, so a boot's own mark is the right kind at once.

    Boot recovery is the reachable way to get there: a deployment that mistyped a tier reaches
    that loop before it ever escalates, and the mark it writes is what decides whether every pass
    for the life of the process spends a control call on it.
    """
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST])
    manager = _manager(host, _placer(), _plan(evict_models=(_GHOST,)))
    settled = await converge_residency(
        host,
        _plan(evict_models=(_GHOST,)),
        manager.standing_tiers,
        clock=_FixedClock(),
        sleeper=RecordingSleeper(),
    )
    assert settled is True  # the cortex is fine; a peer nobody hosts is not its verdict
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED


async def test_a_replaced_daemon_asks_an_unhosted_tier_again() -> None:
    """The one event that can grow a roster rebuilds the record, which is the clearing path.

    Nothing was built for it: the boot watch already converges residency when the daemon under
    this brain turns out to be a different one, and that convergence ends in the restart loop that
    asks every peer to run.
    """
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST], boot_id="first")
    plan = _plan(evict_models=(_GHOST,))
    manager = _manager(host, _placer(), plan)
    await manager.heal_residency()
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    host.unhosted.clear()  # the operator named an artifact and the sidecar restarted
    host.boot = "second"
    async with manager.swap_scope("brain"):
        pass
    assert manager.standing_tiers.missing == ()


async def test_a_pass_that_finds_every_tier_serving_writes_nothing_and_starts_nothing() -> None:
    """The ordinary pass, and the whole cost of the sweep: one status per evictable tier."""
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER, _OTHER_TIER])
    manager = _manager(host, placer, _plan(evict_models=(_TIER, _OTHER_TIER)))
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("status", _OTHER_TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_deployment_that_evicts_nothing_still_asks_nobody_anything() -> None:
    """The shipped default: ``CORTEX_SWAP_EVICT_MODELS`` is empty, so a pass costs nothing."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _placer(), _plan(evict_models=()))
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == []


async def test_the_loop_keeps_retrying_until_it_is_closed() -> None:
    """``TierHealer`` is the pacing and the task; a pass is whatever it was handed."""
    passes = asyncio.Event()
    count = 0

    async def one_pass() -> None:
        nonlocal count
        count += 1
        if count >= 2:
            passes.set()

    healer = TierHealer(one_pass, interval_s=0.001)
    healer.start()
    healer.start()  # idempotent: the second call must not put a second loop on the same record
    assert len([task for task in asyncio.all_tasks() if task.get_name() == _LOOP_NAME]) == 1
    try:
        async with asyncio.timeout(5.0):
            await passes.wait()
    finally:
        await healer.aclose()
    assert count >= 2


async def test_a_failing_pass_costs_one_pass_and_not_the_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug nobody enumerated must cost a retry, never the retrying a degraded stack waits on."""
    survived = asyncio.Event()
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "an unenumerated bug"
            raise RuntimeError(msg)
        survived.set()

    healer = TierHealer(flaky, interval_s=0.001)
    with caplog.at_level(logging.ERROR, logger="cortex_core.residency_heal"):
        healer.start()
        try:
            async with asyncio.timeout(5.0):
                await survived.wait()
        finally:
            await healer.aclose()
    assert [record.message for record in caplog.records] == [
        "a residency tier retry failed; the next pass tries again"
    ]


async def test_closing_wakes_the_wait_instead_of_serving_out_the_interval() -> None:
    """Shutdown must not be held for the pacing, which is why the wait is on the stop signal."""
    entered = asyncio.Event()

    async def one_pass() -> None:
        entered.set()

    healer = TierHealer(one_pass, interval_s=3600.0)
    healer.start()
    async with asyncio.timeout(5.0):
        await entered.wait()
        await healer.aclose()  # would sit out the hour if the wait were a plain sleep


async def test_closing_a_loop_that_never_started_is_a_no_op() -> None:
    """The uniform shutdown hook runs whatever the deployment built, started or not."""

    async def one_pass() -> None:  # pragma: no cover -- a loop that never ran never calls it
        raise AssertionError

    await TierHealer(one_pass).aclose()
