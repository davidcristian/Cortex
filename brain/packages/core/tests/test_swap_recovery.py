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
    """What each line says and what fields it has, read the way the formatter reads a record."""
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
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        assert await _recover(handoffs, host) is True
    assert [call for call in host.calls if call[0] != "status"] == []
    assert host.running == {"cortex"}
    assert caplog.records == []


async def test_a_stranded_record_is_failed_so_the_next_handoff_is_not_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    await handoffs.put(_stranded())  # pyright: ignore[reportArgumentType]
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        await _recover(handoffs, host)
    assert await handoffs.active() is None
    failed = await handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED
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
    host = ScriptedModelHost(running=["brain"])
    assert await _recover(RecordingHandoffStore(), host) is True
    assert host.running == {"cortex"}
    assert ("stop", "brain") in host.calls
    assert ("start", "cortex") in host.calls


async def test_an_evictable_tier_is_cleared_off_the_gpu_and_then_put_back() -> None:
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
    assert tiers.missing == ()


async def test_a_cortex_that_will_not_come_back_is_reported_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    assert settled is False
    assert [record.message for record in caplog.records] == [
        "the cortex is not serving after boot recovery; turns will fail until it is"
    ]


async def test_an_unreachable_host_does_not_fail_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    assert settled is False
    assert _said(caplog) == [
        ("the model host failed while clearing the deep model at boot", {"model": "brain"})
    ]
    assert tiers.missing == ()


async def test_a_peer_that_will_not_start_is_recorded_and_not_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    host = ScriptedModelHost(running=["brain", "cortex"], fail={("stop", "brain"): "wedged"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert ("status", "cortex") not in host.calls
    assert _said(caplog) == [
        ("the model host failed while clearing the deep model at boot", {"model": "brain"})
    ]


async def test_a_cortex_the_daemon_does_not_serve_is_amber_and_says_which_it_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(unhosted=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert _said(caplog) == [
        (
            "the model host does not serve the cortex this brain names, so nothing can",
            {"model": "cortex"},
        )
    ]


async def test_a_host_that_fails_at_the_cortex_names_the_cortex_and_not_the_deep_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(fail={("status", "cortex"): "supervisor unreachable"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        settled = await _recover(RecordingHandoffStore(), host)
    assert settled is False
    assert ("status", "brain") in host.calls
    assert _said(caplog) == [
        ("the model host was unreachable during boot recovery", {"model": "cortex"})
    ]


async def test_a_cortex_that_will_not_settle_still_asks_for_its_peers_back() -> None:
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
    class _Unreadable(RecordingHandoffStore):
        async def active(self) -> None:
            msg = "redis is down at boot"
            raise HandoffStoreError(msg)

    host = ScriptedModelHost(running=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        assert await _recover(_Unreadable(), host) is True
    assert [record.message for record in caplog.records] == [
        "could not read or fail a stranded handoff at startup"
    ]
    assert host.running == {"cortex"}
