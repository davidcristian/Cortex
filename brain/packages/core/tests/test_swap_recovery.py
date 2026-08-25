"""Boot recovery: what a restart owes a handoff the process did not survive.

The chaos suite proves the conductor converges every path it is still running; this proves the
one it cannot, because the process died. A restart fails the stranded record and converges the
GPU back onto the cortex, and it never resumes a deep phase, because replaying side-effectful
work without a request-identity design is the worse failure.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- skipping the ``transition`` to FAILED reddens
  ``test_a_stranded_record_is_failed_so_the_next_handoff_is_not_refused``;
- skipping the stop of a still-running deep model reddens
  ``test_a_deep_model_left_resident_by_a_crash_is_stopped``;
- leaving an evicted tier stopped instead of restoring it reddens
  ``test_an_evictable_tier_is_cleared_off_the_gpu_and_then_put_back``;
- letting a ``ModelHostError`` escape reddens ``test_an_unreachable_host_does_not_fail_the_boot``.

Convergence also answers whether the cortex was observed serving, which the composition root
publishes onto the residency report (a log line nobody reads is not a readiness surface). One
more measured mutation: returning ``True`` unconditionally reddens 4 (re-measured 2026-08-09,
having been 3 before a third such case was added here), every case that observes a cortex which is
not serving, here and in ``test_residency_watch.py``, plus the composition root's
``test_a_boot_that_could_not_settle_the_cortex_leaves_the_seam_saying_so``.

That answer is about the cortex alone, which is three cases here plus three mutations, each applied
to production code alone with the whole brain workspace re-run, so the counts are measured:

- letting a peer's refused ``start`` decide the verdict again (starting the evicted tiers back
  inside the same ``try``, which is what this did before) reddens **5**: three here
  (``..._will_not_start_is_recorded_and_not_counted``, ``..._does_not_serve_at_all_is_no_verdict``,
  ``..._still_asks_for_its_peers_back``),
  ``test_a_peer_the_fresh_daemon_will_not_run_is_recorded_and_the_handoff_proceeds`` in
  ``test_residency_watch.py``, and the composition root's
  ``test_a_boot_whose_peer_tier_is_down_still_says_the_brain_is_ready``;
- letting a peer's refused ``status`` do the same (the clearing loop back inside that ``try``,
  deep model included) reddens **1**,
  ``test_a_peer_the_daemon_does_not_serve_at_all_is_no_verdict_either``, which is the only case
  that fails one call earlier than the rest and the one a real sidecar produces;
- marking the peers after an unreachable host too (calling ``restart_evicted`` before the
  ``except``'s ``return``) reddens **1**, ``test_an_unreachable_host_does_not_fail_the_boot``.

That last case is why it names a peer tier and hands the host a start it refuses. Written the
obvious way, over this file's default plan, its last assertion was **vacuous**: that plan evicts
nothing, so the mutation had no tier to mark and stayed green. Every path here that asserts on the
record needs a plan with a peer in it, which is the shape the shipped defaults do not have.

The deep tier is the one peer of none, and a host that does not carry it at all is the one failure
of its clearing that says nothing about the card (ADR-0030 unrostered-tier addendum). Two more
measured mutations, one per direction:

- making that clearing fatal again (re-raising the ``ModelNotHostedError`` instead of logging it)
  reddens **1**, ``..._is_a_config_fault_not_an_amber_boot``;
- answering ``True`` where a cortex the daemon does not serve is caught reddens **1**,
  ``..._is_amber_and_says_which_it_is``, which is the guard on the whole change: the tolerance is
  for a tier nothing can be resident under, never for the model that has to be.

Three more for the model a failure names, measured once the clearing and the settling stopped
sharing a ``try``, each applied to production code alone with the whole brain workspace re-run:

- naming the cortex on the deep model's clearing reddens **2**,
  ``..._an_unreachable_host_does_not_fail_the_boot`` and
  ``..._a_deep_model_that_really_will_not_stop_still_fails_the_boot``, the two cases that fail at
  the deep model;
- naming the deep model on the cortex's own failure reddens **1**,
  ``..._a_host_that_fails_at_the_cortex_names_the_cortex_and_not_the_deep_model``;
- putting both calls back under one ``try`` reddens **2**, the same two deep-model cases and
  **not** the cortex one, which is why they are the pair that has to exist: a cortex that fails
  last is the model a collapsed arm happens to name, so a suite holding only the new case would
  let the collapse back in.

One more, measured 2026-08-24 over ``brain/``: reverting the stranded line's work field to the
bare ``handoff`` it used to spell reddens **1**,
``..._a_stranded_record_is_failed_so_the_next_handoff_is_not_refused``, whose assertion moved
from the message alone to the whole record when the swap path joined the log vocabulary (ADR-0009
sixth-name addendum).
"""

import logging

import pytest
import swap_harness as harness
from swap_harness import RecordingHandoffStore, TickingClock

from cortex_core import (
    HandoffState,
    HandoffStoreError,
    ModelHostState,
    PlainFormatter,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    StandingTiers,
    SystemClock,
    converge_residency,
    record_fields,
    recover_handoffs,
)

_TIER = "subagent-gpu"


def _said(caplog: pytest.LogCaptureFixture) -> list[tuple[str, dict[str, object]]]:
    """What each line says and what it carries, read the way the formatter reads a record.

    The message alone is not the assertion these cases want any more. A boot failure's whole job
    is to name the tier the host refused, and that name rides as a field, so a check on the
    sentence would pass just as well on a line that named the other model.
    """
    return [(record.message, record_fields(record)) for record in caplog.records]


async def _recover(
    handoffs: RecordingHandoffStore,
    host: ScriptedModelHost,
    tiers: StandingTiers | None = None,
    plan: ResidencyPlan | None = None,
) -> bool:
    return await recover_handoffs(
        handoffs,
        host,
        plan if plan is not None else harness.plan(),
        tiers if tiers is not None else StandingTiers(),
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )


def _stranded() -> object:
    return harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )


async def test_a_clean_boot_touches_nothing(caplog: pytest.LogCaptureFixture) -> None:
    """The usual case: no handoff was in flight and the cortex is already serving."""
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        assert await _recover(handoffs, host) is True  # what the seam then publishes as ready
    assert [call for call in host.calls if call[0] != "status"] == []
    assert host.running == {"cortex"}
    assert caplog.records == []


async def test_a_stranded_record_is_failed_so_the_next_handoff_is_not_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A live record would make ``active()`` refuse every later escalation forever.

    The line names the stranded work as a turn, which is what it is: a handoff id is the
    escalating turn's id (ADR-0009 sixth-name addendum), and this boot is the one reader who
    can still carry that id back to the previous process's own lines about the same turn.
    """
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    await handoffs.put(_stranded())  # pyright: ignore[reportArgumentType]
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        await _recover(handoffs, host)
    assert await handoffs.active() is None
    failed = await handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED  # kept, not deleted: it is the diagnosis
    assert _said(caplog) == [
        (
            "a handoff did not survive the restart; marking it failed",
            {
                "session_id": harness.SESSION,
                "turn_id": harness.TURN,
                "state": HandoffState.READY.value,
            },
        )
    ]


async def test_a_deep_model_left_resident_by_a_crash_is_stopped() -> None:
    """The GPU is converged to where the conductor's finally would have left it."""
    host = ScriptedModelHost(running=["brain"])
    assert await _recover(RecordingHandoffStore(), host) is True
    assert host.running == {"cortex"}
    assert ("stop", "brain") in host.calls
    assert ("start", "cortex") in host.calls


async def test_an_evictable_tier_is_cleared_off_the_gpu_and_then_put_back() -> None:
    """The order is the conductor's: clear the GPU, settle the cortex, restore the rest.

    A crash can leave a tier holding VRAM the cortex needs, so it goes first; but the standing
    residency includes it, so a boot that left it stopped would silently shrink the machine.
    """
    host = ScriptedModelHost(running=[_TIER, "brain", "cortex"])
    tiers = StandingTiers()
    settled = await converge_residency(
        host,
        harness.plan(evict_models=(_TIER,)),
        tiers,
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )
    assert settled is True
    assert [call for call in host.calls if call[0] != "status"] == [
        ("stop", _TIER),
        ("stop", "brain"),
        ("start", _TIER),
    ]
    assert host.running == {"cortex", _TIER}
    assert tiers.missing == ()  # a peer that came back is nothing to record


async def test_a_cortex_that_will_not_come_back_is_reported_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recovery cannot fix a host that will not serve, so it says so instead of pretending."""
    host = ScriptedModelHost(status_override={"cortex": ModelHostState.LOADING})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await recover_handoffs(
            RecordingHandoffStore(),
            host,
            harness.plan(load_timeout_s=0.0),
            StandingTiers(),
            clock=TickingClock(),
            sleeper=RecordingSleeper(),
        )
    assert settled is False  # the answer the composition root turns into an amber dot
    assert [record.message for record in caplog.records] == [
        "the cortex is not serving after boot recovery; turns will fail until it is"
    ]


async def test_an_unreachable_host_does_not_fail_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dead supervisor is logged and served around: the brain still starts and answers RPCs.

    Dead to every call, which is what makes the last assertion mean something: this plan names a
    peer tier and this host would refuse to start it, so a convergence that asked anyway would
    have something to record.

    The dead call this reaches first is the deep model's ``status``, so the line names the deep
    model. That is the point of the narrowing: a host that is dead to everything is still refusing
    one call at a time, and the boot says which one it was rather than which one it might have
    been.
    """
    host = ScriptedModelHost(
        fail={
            ("status", "brain"): "supervisor unreachable",
            ("start", _TIER): "supervisor unreachable",
        }
    )
    tiers = StandingTiers()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(
            RecordingHandoffStore(), host, tiers, harness.plan(evict_models=(_TIER,))
        )
    # Nothing was observed about the cortex, and the honest report of an unobserved GPU is amber.
    assert settled is False
    assert _said(caplog) == [
        ("the model host failed while clearing the deep model at boot", {"model": "brain"})
    ]
    # And nothing was observed about the peers either: a host that could not be reached was never
    # asked to run one, and this record's one rule is that only a refusal marks.
    assert tiers.missing == ()


async def test_a_peer_that_will_not_start_is_recorded_and_not_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The whole fix: a delegation tier that is broken is not the usual assistant being gone.

    The cortex was observed serving, so the verdict this returns is ``True`` and the seam stays
    green. What the boot did learn is written where every other writer writes it, so the placer
    stops offering the GPU and the retry loop has the tier to work on from its first pass.
    """
    host = ScriptedModelHost(running=["cortex"], fail={("start", _TIER): "no such device"})
    tiers = StandingTiers()
    with caplog.at_level(logging.ERROR, logger="cortex_core.residency_moves"):
        settled = await converge_residency(
            host,
            harness.plan(evict_models=(_TIER,)),
            tiers,
            clock=TickingClock(),
            sleeper=RecordingSleeper(),
        )
    assert settled is True
    assert tiers.missing == (_TIER,)
    assert [record.message for record in caplog.records] == [
        "a tier evicted for the handoff could not be restarted"
    ]


async def test_a_peer_the_daemon_does_not_serve_at_all_is_no_verdict_either(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The reachable misconfiguration, and the reason the clearing phase is peer-tolerant too.

    A tier named in ``CORTEX_SWAP_EVICT_MODELS`` that the sidecar has no artifact for is not in
    that daemon's roster, so it answers 404 to every verb, ``status`` included. Guarding only the
    restart would have left this boot answering that the cortex was gone, one call before it was
    ever asked about, which is what a real sidecar was observed doing.
    """
    host = ScriptedModelHost(
        running=["cortex"],
        fail={("status", _TIER): "unknown model", ("start", _TIER): "unknown model"},
    )
    tiers = StandingTiers()
    with caplog.at_level(logging.ERROR):
        settled = await converge_residency(
            host,
            harness.plan(evict_models=(_TIER,)),
            tiers,
            clock=TickingClock(),
            sleeper=RecordingSleeper(),
        )
    assert settled is True
    assert tiers.missing == (_TIER,)
    assert [record.message for record in caplog.records] == [
        "a tier the standing residency includes could not be cleared at boot",
        "a tier evicted for the handoff could not be restarted",
    ]


async def test_a_deep_tier_the_daemon_does_not_serve_is_a_config_fault_not_an_amber_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The whole of this fix: escalation declared with no artifact behind it is not an outage.

    ``CORTEX_ESCALATION`` on and ``CORTEX_MODEL_FILE_BRAIN`` naming nothing leaves the deep tier
    out of the daemon's roster, so its every verb answers 404 for the life of that container.
    Nothing holds the card under a name nothing can start, so the cortex answers for itself and
    the deployment is told once what it has actually configured.
    """
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is True
    assert host.running == {"cortex"}
    # Said once, at ERROR, naming both knobs that produce the state and the one it does not touch.
    # Asserted on the whole line the entry point's formatter renders, because which tier it was
    # and what the host said are fields now: the message used to spell them a second time, which
    # is the same reading printed twice once a formatter renders what a record carries.
    assert [PlainFormatter().format(record) for record in caplog.records] == [
        "ERROR:cortex_core.swap_recovery:escalation is enabled but the model host does not serve "
        "the deep model, so no handoff can ever run: name an artifact for that tier "
        "(CORTEX_MODEL_FILE_BRAIN) or turn escalation off (CORTEX_ESCALATION); the cortex is "
        "unaffected error=\"unknown model 'brain'; this twin was told it does not host it\" "
        "model=brain"
    ]


async def test_a_deep_model_that_really_will_not_stop_still_fails_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The failure the fix must not introduce: a real outage reading as a configuration choice.

    A deep model that is resident and whose ``stop`` fails is the case the whole asymmetry exists
    for, because the card may still be holding it, and it stays amber without the cortex being
    asked about at all.
    """
    host = ScriptedModelHost(running=["brain", "cortex"], fail={("stop", "brain"): "wedged"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert ("status", "cortex") not in host.calls
    # The wedged tier is the deep model, and the line says so: the cortex was never even asked
    # about here, so a failure naming it would be an invention.
    assert _said(caplog) == [
        ("the model host failed while clearing the deep model at boot", {"model": "brain"})
    ]


async def test_a_cortex_the_daemon_does_not_serve_is_amber_and_says_which_it_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The same distinction pointing the other way, which must not turn green.

    A daemon whose roster lacks the cortex is a misconfiguration too, and it is the one where
    nothing is serving turns: the verdict is the amber every unconfirmed cortex gets, and only the
    log separates it from a host that could not be reached.
    """
    host = ScriptedModelHost(unhosted=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    # The one arm that could always name its model, and now the only call it wraps is the
    # cortex's, so the name is structural rather than a fact read out of another function.
    assert _said(caplog) == [
        (
            "the model host does not serve the cortex this brain names, so nothing can",
            {"model": "cortex"},
        )
    ]


async def test_a_host_that_fails_at_the_cortex_names_the_cortex_and_not_the_deep_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The other half of the narrowing, and the case the old single ``try`` could not tell apart.

    The deep model is already off the card, so the clearing passes and the refusal lands on the
    cortex's own ``status``. One block ago this said the same sentence as a wedged deep model and
    named nothing; naming the deep model here would send an operator to restart a tier that is
    behaving perfectly.
    """
    host = ScriptedModelHost(fail={("status", "cortex"): "supervisor unreachable"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert ("status", "brain") in host.calls  # the clearing really did run and really did pass
    assert _said(caplog) == [
        ("the model host was unreachable during boot recovery", {"model": "cortex"})
    ]


async def test_a_cortex_that_will_not_settle_still_asks_for_its_peers_back() -> None:
    """The two verdicts are independent in both directions, not only the interesting one.

    A boot that cannot confirm the cortex is amber whatever the peers do, and leaving the peers
    stopped on top of that would shrink the machine for the sake of a failure they had no part
    in: the tier is asked for, comes back, and is recorded standing.
    """
    host = ScriptedModelHost(running=[_TIER], status_override={"cortex": ModelHostState.LOADING})
    tiers = StandingTiers()
    tiers.mark_missing(_TIER)
    settled = await converge_residency(
        host,
        harness.plan(evict_models=(_TIER,), load_timeout_s=0.0),
        tiers,
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )
    assert settled is False
    assert ("start", _TIER) in host.calls
    assert tiers.missing == ()


async def test_an_unreadable_handoff_store_does_not_fail_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Same posture for the store: log it, converge residency anyway, keep serving."""

    class _Unreadable(RecordingHandoffStore):
        async def active(self) -> None:
            msg = "redis is down at boot"
            raise HandoffStoreError(msg)

    host = ScriptedModelHost(running=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        assert await _recover(_Unreadable(), host) is True  # the GPU is fine; only redis was not
    assert [record.message for record in caplog.records] == [
        "could not read or fail a stranded handoff at startup"
    ]
    assert host.running == {"cortex"}
