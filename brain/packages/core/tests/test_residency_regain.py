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
    PlainFormatter,
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
_NO_CORTEX_READING = "the model host could not be asked whether the cortex is serving again"
_NO_DEEP_READING = "the model host could not be asked whether the deep model is still resident"
_REFUSED = "connection refused"


class _FixedClock:
    """A clock that never advances; every wait here ends on a state or an expired deadline."""

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
    """A host whose cortex starts and then never serves, so the restore gives up."""
    fields: dict[str, object] = {
        "running": [_CORTEX],
        "status_override": {_CORTEX: ModelHostState.FAILED},
    }
    return ScriptedModelHost(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _regain_log(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Only this module's own lines, each case having first run a swap that logged a failure."""
    return [record.msg for record in caplog.records if record.name == _REGAIN_LOGGER]


def _regain_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The same lines as an operator sees them, fields included."""
    return [
        PlainFormatter().format(record)
        for record in caplog.records
        if record.name == _REGAIN_LOGGER
    ]


async def _give_up(manager: SwappingModelManager) -> None:
    """Run one handoff whose swap back fails twice."""
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope(_DEEP):
            pass  # pragma: no cover -- a failed swap in never runs the scope's body
    assert manager.residency() == RESIDENCY_LOST


async def _refuses_every_turn(manager: SwappingModelManager) -> None:
    """Check the dead end: no turn can run at all."""
    with pytest.raises(ModelUnavailableError, match="resident: None"):
        async with manager.acquire(_CORTEX):
            pass  # pragma: no cover -- the acquire raises before the body runs


async def _serves_turns_again(manager: SwappingModelManager) -> None:
    """Check the recovery: the lease hands out the cortex again."""
    async with manager.acquire(_CORTEX) as lease:
        assert lease.endpoint == _ENDPOINTS[_CORTEX]


def _placer() -> VramBudgetPlacer:
    """3.0 GiB of headroom beside the cortex, so the 2.0 GiB subagent below fits the GPU."""
    return VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)


def _spawn() -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)


async def test_a_restore_that_gave_up_is_regained_by_the_next_pass_with_no_restart(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = _stalled_host()
    manager = _manager(host)
    await _give_up(manager)
    await _refuses_every_turn(manager)
    host.set_status(_CORTEX, None)
    host.calls.clear()
    with caplog.at_level(logging.INFO, logger=_REGAIN_LOGGER):
        await manager.recheck_residency()
    assert host.calls == [("status", _CORTEX), ("status", _DEEP)]
    assert manager.residency() == RESIDENCY_SERVING
    await _serves_turns_again(manager)
    assert _regain_log(caplog) == [_REGAINED]


async def test_a_serving_report_costs_the_pass_no_control_call_at_all() -> None:
    host = ScriptedModelHost(running=[_CORTEX])
    manager = _manager(host)
    host.calls.clear()
    await manager.recheck_residency()
    assert host.calls == []
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_cortex_that_is_not_serving_yet_leaves_the_report_where_it_was() -> None:
    host = _stalled_host()
    manager = _manager(host)
    await _give_up(manager)
    host.calls.clear()
    await manager.recheck_residency()
    assert host.calls == [("status", _CORTEX)]
    assert manager.residency() == RESIDENCY_LOST
    await _refuses_every_turn(manager)


@pytest.mark.parametrize("deep_state", [ModelHostState.READY, ModelHostState.LOADING])
async def test_a_deep_model_still_on_the_card_stops_the_regain(
    deep_state: ModelHostState,
) -> None:
    host = _stalled_host(
        status_override={_CORTEX: ModelHostState.FAILED, _DEEP: deep_state},
        fail={("stop", _DEEP): "still resident"},
    )
    manager = _manager(host)
    await _give_up(manager)
    host.running.add(_CORTEX)
    host.set_status(_CORTEX, None)
    host.calls.clear()
    await manager.recheck_residency()
    assert host.calls == [("status", _CORTEX), ("status", _DEEP)]
    assert manager.residency() == RESIDENCY_LOST
    await _refuses_every_turn(manager)


async def test_a_deep_tier_the_daemon_never_had_is_off_the_card() -> None:
    host = _stalled_host(unhosted=[_DEEP])
    manager = _manager(host)
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    await manager.recheck_residency()
    assert manager.residency() == RESIDENCY_SERVING
    await _serves_turns_again(manager)


async def test_a_host_that_cannot_be_asked_about_the_cortex_publishes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=[_CORTEX], fail={("status", _CORTEX): _REFUSED})
    manager = _manager(host)
    await _give_up(manager)
    host.calls.clear()
    with caplog.at_level(logging.DEBUG, logger=_REGAIN_LOGGER):
        await manager.recheck_residency()
    assert host.calls == [("status", _CORTEX)]
    assert manager.residency() == RESIDENCY_LOST
    assert _regain_lines(caplog) == [
        f'DEBUG:{_REGAIN_LOGGER}:{_NO_CORTEX_READING} error="{_REFUSED}" model={_CORTEX}'
    ]


async def test_a_host_that_cannot_be_asked_about_the_deep_model_publishes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = _stalled_host(fail={("status", _DEEP): _REFUSED})
    manager = _manager(host)
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    with caplog.at_level(logging.DEBUG, logger=_REGAIN_LOGGER):
        await manager.recheck_residency()
    assert manager.residency() == RESIDENCY_LOST
    assert _regain_lines(caplog) == [
        f'DEBUG:{_REGAIN_LOGGER}:{_NO_DEEP_READING} error="{_REFUSED}" model={_DEEP}'
    ]


async def test_a_handoff_that_begins_mid_pass_wins_the_publish() -> None:
    host = ScriptedModelHost(running=[_CORTEX], pause_at=[("status", _DEEP)])
    manager = _manager(host)
    await manager.publish_boot_residency(serving=False)
    reached, release = host.reached[("status", _DEEP)], host.release[("status", _DEEP)]
    first = asyncio.create_task(manager.recheck_residency())
    async with asyncio.timeout(5.0):
        await reached.wait()
        async with manager.handoff_claim():
            release.set()
            await first
            assert manager.residency() == RESIDENCY_BOOT_FAILED
        await manager.recheck_residency()
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_pass_rechecks_the_peers_before_it_republishes_the_resident() -> None:
    host = _stalled_host()
    manager = _manager(host, plan=_plan(evict_models=(_TIER,)))
    await _give_up(manager)
    host.set_status(_CORTEX, None)
    host.calls.clear()
    await manager.recheck_residency()
    assert host.calls == [
        ("status", _TIER),
        ("start", _TIER),
        ("status", _CORTEX),
        ("status", _DEEP),
    ]
    report = manager.residency()
    assert report.serving is True
    assert report.detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    await manager.recheck_residency()
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_regained_residency_charges_the_placer_for_the_cortex_again() -> None:
    placer = _placer()
    host = _stalled_host(device_memory=DeviceMemory(free_mib=20000, total_mib=24000))
    manager = _manager(host, placer, _plan(brain_vram_mib=13312))
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    await _give_up(manager)
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.set_status(_CORTEX, None)
    await manager.recheck_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_boot_that_could_not_confirm_the_cortex_goes_green_when_it_comes_up() -> None:
    host = ScriptedModelHost(running=[_CORTEX])
    manager = _manager(host)
    await manager.publish_boot_residency(serving=False)
    assert manager.residency() == RESIDENCY_BOOT_FAILED
    await _serves_turns_again(manager)
    await manager.recheck_residency()
    assert manager.residency() == RESIDENCY_SERVING
