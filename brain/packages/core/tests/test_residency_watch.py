import logging

import pytest
from swap_harness import TickingClock

from cortex_core import (
    RESIDENCY_LOST,
    RESIDENCY_SERVING,
    ControlBounds,
    ModelHostState,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyReport,
    ScriptedModelHost,
    StandingTiers,
    SwapFailedError,
    record_fields,
)
from cortex_core.residency_watch import BootWatch

# The shipped bounds, and a sidecar retuned past them: 5 + 20 + 35 comes to exactly the 60 s
# control deadline, which is the mistuning these tests check for.
_SHIPPED = ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
_RETUNED = ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "load_timeout_s": 60.0,
        "control_deadline_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


class _Published:
    """The manager's one residency writer, recording what it was asked to publish."""

    def __init__(self) -> None:
        self.writes: list[tuple[str | None, ResidencyReport]] = []

    async def __call__(self, model: str | None, report: ResidencyReport) -> None:
        self.writes.append((model, report))


def _watch(
    host: ScriptedModelHost, plan: ResidencyPlan | None = None, tiers: StandingTiers | None = None
) -> BootWatch:
    return BootWatch(
        host,
        plan if plan is not None else _plan(),
        tiers if tiers is not None else StandingTiers(),
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )


def test_a_first_answer_is_a_seed_and_never_a_change() -> None:
    watch = _watch(ScriptedModelHost())
    assert watch.observe("daemon-a") is False
    assert watch.observe("daemon-a") is False
    assert watch.observe("daemon-b") is True


def test_a_host_that_will_not_say_is_no_evidence_in_either_direction() -> None:
    watch = _watch(ScriptedModelHost())
    assert watch.observe(None) is False
    assert watch.observe("daemon-a") is False
    assert watch.observe(None) is False
    assert watch.observe("daemon-b") is True


async def test_the_boot_seed_records_who_answered_without_converging_anything() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a")
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    assert host.calls == [("boot_id", "")]
    assert published.writes == []
    await watch.reconcile(published)
    assert host.calls == [("boot_id", ""), ("boot_id", "")]
    assert published.writes == []


async def test_the_same_daemon_answering_again_costs_one_read_and_changes_nothing() -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"], boot_id="daemon-a")
    watch = _watch(host, _plan(evict_models=("subagent-gpu",)))
    published = _Published()
    await watch.seed()
    await watch.reconcile(published)
    await watch.reconcile(published)
    assert [op for op, _ in host.calls] == ["boot_id", "boot_id", "boot_id"]
    assert host.running == {"cortex", "subagent-gpu"}
    assert published.writes == []


async def test_a_replaced_daemon_is_converged_and_the_finding_is_published(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a")
    watch = _watch(host, _plan(evict_models=("subagent-gpu",)))
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        await watch.reconcile(published)
    assert "the model host has been replaced since the last handoff" in caplog.text
    assert host.running == {"cortex", "subagent-gpu"}
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_a_peer_the_fresh_daemon_will_not_run_is_recorded_and_the_handoff_proceeds() -> None:
    host = ScriptedModelHost(
        running=["cortex"], boot_id="daemon-a", fail={("start", "subagent-gpu"): "no such device"}
    )
    tiers = StandingTiers()
    watch = _watch(host, _plan(evict_models=("subagent-gpu",)), tiers)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]
    assert tiers.missing == ("subagent-gpu",)


async def test_one_restart_is_reconciled_once_however_many_handoffs_follow() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a")
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    await watch.reconcile(published)
    await watch.reconcile(published)
    await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_a_replaced_daemon_that_cannot_be_converged_refuses_the_handoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex"],
        boot_id="daemon-a",
        status_override={"cortex": ModelHostState.LOADING},
    )
    watch = _watch(host, _plan(load_timeout_s=0.0))
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    with (
        caplog.at_level(logging.ERROR, logger="cortex_core.residency_watch"),
        pytest.raises(SwapFailedError, match="residency could not be converged"),
    ):
        await watch.reconcile(published)
    assert published.writes == [(None, RESIDENCY_LOST)]
    refused = caplog.records[-1]
    assert refused.name == "cortex_core.residency_watch"
    assert refused.message == (
        "the model host was replaced and residency could not be converged onto the cortex"
    )
    assert record_fields(refused) == {"model": "cortex"}


async def test_a_daemon_that_came_back_with_bounds_the_deadline_cannot_clear_refuses() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a", control_bounds=_SHIPPED)
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    host.bounds = _RETUNED
    with pytest.raises(SwapFailedError, match=r"worst stop of 60\.0 s"):
        await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]
    assert host.running == {"cortex"}


async def test_a_daemon_that_came_back_within_the_deadline_runs_the_handoff() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a", control_bounds=_RETUNED)
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    host.bounds = _SHIPPED
    await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_a_daemon_that_states_no_bounds_leaves_the_pairing_with_nothing_to_check() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a")
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_a_plan_that_declared_no_deadline_states_no_rule_to_check() -> None:
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a", control_bounds=_RETUNED)
    watch = _watch(host, _plan(control_deadline_s=0.0))
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    await watch.reconcile(published)
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_bounds_that_cannot_be_read_after_a_restart_leave_the_pairing_unchecked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex"],
        boot_id="daemon-a",
        fail={("control_bounds", ""): "the supervisor is wedged"},
    )
    watch = _watch(host)
    published = _Published()
    await watch.seed()
    host.boot = "daemon-b"
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        await watch.reconcile(published)
    assert "could not be asked for its control bounds after a restart" in caplog.text
    assert published.writes == [("cortex", RESIDENCY_SERVING)]


async def test_a_host_that_cannot_be_asked_leaves_every_belief_where_it_was(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex"], fail={("boot_id", ""): "connection refused"}, control_bounds=_RETUNED
    )
    watch = _watch(host)
    published = _Published()
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        await watch.seed()
        await watch.reconcile(published)
    assert "could not be asked which daemon is answering" in caplog.text
    assert published.writes == []
