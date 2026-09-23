import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    DEFAULT_SPILL_DWELL_S,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_SERVING,
    SPILLED_PACE_DETAIL,
    TIERS_MISSING_DETAIL,
    BaselineTiers,
    HandoffPace,
    ModelHostState,
    PaceSink,
    RecordingPaceSink,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyReport,
    ResidencyRestoreError,
    ScriptedModelHost,
    SwappingModelManager,
)

_CORTEX = "cortex"
_DEEP = "brain"
_TIER = "subagent-gpu"
_ENDPOINTS = {_CORTEX: "http://llama-cortex:8080", _DEEP: "http://llama-brain:8081"}
_AT = datetime(2026, 8, 19, 21, 0, tzinfo=UTC)


class _HeldClock:
    """A clock that moves only when a test moves it, so no test ever waits on real time."""

    def __init__(self) -> None:
        self._at = _AT

    def now(self) -> datetime:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += timedelta(seconds=seconds)


def _manager(host: ScriptedModelHost, plan: ResidencyPlan | None = None) -> SwappingModelManager:
    fields: dict[str, object] = {
        "cortex_model": _CORTEX,
        "brain_model": _DEEP,
        "evict_models": (),
        "load_timeout_s": 0.0,
    }
    return SwappingModelManager(
        host,
        _ENDPOINTS,
        plan if plan is not None else ResidencyPlan(**fields),  # pyright: ignore[reportArgumentType]
        _HeldClock(),
        RecordingSleeper(),
    )


@dataclass(frozen=True, slots=True)
class PaceSinkUnderTest:
    """One implementation of ``PaceSink``, and how to read back what it was told."""

    sink: PaceSink
    spill_stands: Callable[[], bool]


def _fake_under_test() -> PaceSinkUnderTest:
    fake = RecordingPaceSink()
    return PaceSinkUnderTest(fake, lambda: bool(fake.reported) and fake.reported[-1])


def _record_under_test() -> PaceSinkUnderTest:
    record = HandoffPace(_HeldClock())
    return PaceSinkUnderTest(record, lambda: record.note_on(RESIDENCY_SERVING).detail != "")


_IMPLEMENTATIONS = [_fake_under_test, _record_under_test]


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_a_sink_starts_with_nothing_to_say(build: Callable[[], PaceSinkUnderTest]) -> None:
    assert build().spill_stands() is False


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_the_last_result_written_is_the_one_that_stands(
    build: Callable[[], PaceSinkUnderTest],
) -> None:
    under = build()
    under.sink.note_pace(spilled=True)
    assert under.spill_stands() is True
    under.sink.note_pace(spilled=False)
    assert under.spill_stands() is False
    under.sink.note_pace(spilled=True)
    assert under.spill_stands() is True


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_writing_the_same_result_twice_says_the_same_thing(
    build: Callable[[], PaceSinkUnderTest],
) -> None:
    under = build()
    under.sink.note_pace(spilled=True)
    under.sink.note_pace(spilled=True)
    assert under.spill_stands() is True
    under.sink.note_pace(spilled=False)
    under.sink.note_pace(spilled=False)
    assert under.spill_stands() is False


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_no_implementation_of_the_port_may_await(
    build: Callable[[], PaceSinkUnderTest],
) -> None:
    assert not inspect.iscoroutinefunction(build().sink.note_pace)


def test_a_spill_is_sent_with_a_serving_report_and_names_what_it_costs() -> None:
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    assert pace.note_on(RESIDENCY_SERVING) == ResidencyReport(
        serving=True, detail=SPILLED_PACE_DETAIL
    )


@pytest.mark.parametrize("report", [RESIDENCY_LOADING, RESIDENCY_DEEP, RESIDENCY_LOST])
def test_a_spill_never_speaks_over_a_swap_that_is_in_flight(report: ResidencyReport) -> None:
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    assert pace.note_on(report) is report


def test_a_note_stands_for_the_whole_dwell_and_not_a_moment_longer() -> None:
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=DEFAULT_SPILL_DWELL_S)
    pace.note_pace(spilled=True)
    clock.advance(DEFAULT_SPILL_DWELL_S - 1)
    assert pace.note_on(RESIDENCY_SERVING).detail == SPILLED_PACE_DETAIL
    clock.advance(1)
    assert pace.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


def test_a_second_spill_starts_the_dwell_again_from_when_it_happened() -> None:
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=100.0)
    pace.note_pace(spilled=True)
    clock.advance(99)
    pace.note_pace(spilled=True)
    clock.advance(99)
    assert pace.note_on(RESIDENCY_SERVING).detail == SPILLED_PACE_DETAIL


def test_a_handoff_that_held_its_pace_clears_a_current_note_at_once() -> None:
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=100.0)
    pace.note_pace(spilled=True)
    clock.advance(1)
    pace.note_pace(spilled=False)
    assert pace.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


@pytest.mark.parametrize("dwell_s", [0.0, -1.0])
def test_a_dwell_that_could_never_stand_is_refused(dwell_s: float) -> None:
    with pytest.raises(ValueError, match="dwell_s must be > 0"):
        HandoffPace(_HeldClock(), dwell_s=dwell_s)


def test_a_missing_peer_and_a_spilled_handoff_are_both_said() -> None:
    tiers = BaselineTiers()
    tiers.mark_missing(_TIER)
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    composed = pace.note_on(tiers.note_on(RESIDENCY_SERVING))
    assert composed.serving is True
    assert composed.detail == (
        f"{TIERS_MISSING_DETAIL.format(models=_TIER)}; {SPILLED_PACE_DETAIL}"
    )


async def test_a_spilled_handoff_reaches_a_probe_through_the_manager() -> None:
    manager = _manager(ScriptedModelHost(running=[_CORTEX]))
    assert manager.residency() == RESIDENCY_SERVING
    manager.handoff_pace.note_pace(spilled=True)
    assert manager.residency() == ResidencyReport(serving=True, detail=SPILLED_PACE_DETAIL)


async def test_the_pass_that_republishes_a_serving_cortex_does_not_erase_the_note() -> None:
    host = ScriptedModelHost(running=[_CORTEX], status_override={_CORTEX: ModelHostState.FAILED})
    manager = _manager(host)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope(_DEEP):
            pass  # pragma: no cover -- a failed swap in never runs the scope's body
    assert manager.residency() == RESIDENCY_LOST
    manager.handoff_pace.note_pace(spilled=True)
    host.set_status(_CORTEX, None)
    await manager.recheck_residency()
    assert manager.residency() == ResidencyReport(serving=True, detail=SPILLED_PACE_DETAIL)


async def test_a_probe_reads_a_missing_peer_and_a_spill_off_one_swap() -> None:
    host = ScriptedModelHost(running=[_CORTEX, _TIER], fail={("start", _TIER): "no such device"})
    plan = ResidencyPlan(
        cortex_model=_CORTEX, brain_model=_DEEP, evict_models=(_TIER,), load_timeout_s=0.0
    )
    manager = _manager(host, plan)
    async with manager.swap_scope(_DEEP):
        manager.handoff_pace.note_pace(spilled=True)
    report = manager.residency()
    assert report.serving is True
    assert report.detail == f"{TIERS_MISSING_DETAIL.format(models=_TIER)}; {SPILLED_PACE_DETAIL}"
