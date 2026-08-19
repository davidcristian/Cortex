"""Boot recovery: what a restart owes a handoff the process did not survive."""

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
    recover_handoffs,
)

_TIER = "subagent-gpu"


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
    """A live record would make ``active()`` refuse every later escalation forever."""
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    await handoffs.put(_stranded())  # pyright: ignore[reportArgumentType]
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        await _recover(handoffs, host)
    assert await handoffs.active() is None
    failed = await handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED  # kept, not deleted: it is the diagnosis
    assert [record.message for record in caplog.records] == [
        "a handoff did not survive the restart; marking it failed"
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
    """A dead supervisor is logged and served around: the brain still starts and answers RPCs."""
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
    assert [record.message for record in caplog.records] == [
        "the model host was unreachable during boot recovery"
    ]
    # And nothing was observed about the peers either: a host that could not be reached was never
    # asked to run one, and this record's one rule is that only a refusal marks.
    assert tiers.missing == ()


async def test_a_peer_that_will_not_start_is_recorded_and_not_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The whole fix: a delegation tier that is broken is not the usual assistant being gone."""
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
    """The reachable misconfiguration, and the reason the clearing phase is peer-tolerant too."""
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
    """The whole of this fix: escalation declared with no artifact behind it is not an outage."""
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is True
    assert host.running == {"cortex"}
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
    """The failure the fix must not introduce: a real outage reading as a configuration choice."""
    host = ScriptedModelHost(running=["brain", "cortex"], fail={("stop", "brain"): "wedged"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert ("status", "cortex") not in host.calls
    assert [record.message for record in caplog.records] == [
        "the model host was unreachable during boot recovery"
    ]


async def test_a_cortex_the_daemon_does_not_serve_is_amber_and_says_which_it_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The same distinction pointing the other way, which must not turn green."""
    host = ScriptedModelHost(unhosted=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert [record.message for record in caplog.records] == [
        "the model host does not serve the cortex this brain names, so nothing can"
    ]


async def test_a_cortex_that_will_not_settle_still_asks_for_its_peers_back() -> None:
    """The two verdicts are independent in both directions, not only the interesting one."""
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
