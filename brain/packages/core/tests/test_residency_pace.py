"""A spilled handoff, told to somebody: the port, the record, and how long its note stands.

The unit under test is the path the ADR-0030 spill-note addendum describes, and the cases split
along the two questions that path had to answer. The first is a port question: the deep phase
holds no residency at all, so what it writes to is a ``PaceSink``, and the contract cases below
run over both implementations of it, the fake a test wires and the record a brain wires. The
second is a standing rule: a spill is a fact about **one handoff** while the report it rides is a
fact about **now**, so a note that never cleared would be a second way to be wrong about the card.

The two interactions are what the rest of it is for, and neither is a property of this record
alone, so both are driven through the real ``SwappingModelManager`` over the scripted host:

- the background pass republishes the bare ``RESIDENCY_SERVING`` constant whenever it finds the
  cortex back, which is why the note is composed as a report is read and never written into it;
- a peer that is down and a handoff that spilled can be true at once, have different remedies,
  and are therefore both said rather than one of them winning by whichever wrote last.

Distrust-green proofs (each mutation applied to production code alone, the whole brain workspace
re-run, then reverted, so the counts are measured rather than aimed at):
- dropping the pace note from ``residency()``'s composition reddens 4: the three manager cases
  below plus ``test_health_stays_ready_and_says_the_last_deep_task_ran_far_slower_than_measured``
  at the seam, which is the whole path this exists for;
- letting ``with_note`` annotate a report that is not serving reddens 4, the three cases that
  hold a spill silent through a swap plus ``test_an_evicted_tier_is_not_a_missing_one``, the peer
  record's own version of the same rule;
- letting ``with_note`` replace the note it found instead of joining it reddens 2, both cases
  that assert a down peer and a spilled handoff are said together;
- a note that never lapses reddens 1, the dwell boundary; a second spill that does not re-arm the
  dwell reddens 1, the case that pins the dwell to the handoff rather than to the first spill
  this process ever saw;
- asking ``collapsed`` instead of ``verdict`` in ``BrainPhase._note_pace`` reddens 1,
  ``test_a_deployment_that_declared_no_floor_publishes_no_verdict`` in ``test_brain_phase.py``,
  which is what keeps an opinionless deployment from clearing a real note;
- logging the verdict and publishing nothing, which is the state this entry closes, reddens 3,
  every case in that file's own published-verdict section.
"""

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
    HandoffPace,
    ModelHostState,
    PaceSink,
    RecordingPaceSink,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyReport,
    ResidencyRestoreError,
    ScriptedModelHost,
    StandingTiers,
    SwappingModelManager,
)

_CORTEX = "cortex"
_DEEP = "brain"
_TIER = "subagent-gpu"
_ENDPOINTS = {_CORTEX: "http://llama-cortex:8080", _DEEP: "http://llama-brain:8081"}
_AT = datetime(2026, 8, 19, 21, 0, tzinfo=UTC)


class _HeldClock:
    """A clock that moves only when a test moves it, so a dwell is asserted and never waited on."""

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


# --- The port, over every implementation of it (AGENTS.md: ports before adapters) --------------


@dataclass(frozen=True, slots=True)
class PaceSinkUnderTest:
    """One implementation of ``PaceSink``, and how to read back what it was told.

    The reader differs because the two keep different things on purpose: the fake keeps every
    verdict, since a test's question is what a handoff published, and the record keeps only the
    answer that still stands, since a probe's question is what is true now. What the port promises
    is the same either way, and that is what the cases below state.
    """

    sink: PaceSink
    spill_stands: Callable[[], bool]


def _fake_under_test() -> PaceSinkUnderTest:
    fake = RecordingPaceSink()
    return PaceSinkUnderTest(fake, lambda: bool(fake.verdicts) and fake.verdicts[-1])


def _record_under_test() -> PaceSinkUnderTest:
    record = HandoffPace(_HeldClock())
    return PaceSinkUnderTest(record, lambda: record.note_on(RESIDENCY_SERVING).detail != "")


_IMPLEMENTATIONS = [_fake_under_test, _record_under_test]


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_a_sink_starts_with_nothing_to_say(build: Callable[[], PaceSinkUnderTest]) -> None:
    """A brain that has never escalated has no verdict, which is not the same as a good one."""
    assert build().spill_stands() is False


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_the_last_verdict_written_is_the_one_that_stands(
    build: Callable[[], PaceSinkUnderTest],
) -> None:
    """The port's whole promise: one write per handoff, and the newest handoff is the truth.

    Both directions, because the clearing one is the half that keeps a note from outliving the
    condition it describes: a later handoff that reached its floor is direct evidence the card
    has room again.
    """
    under = build()
    under.sink.note_pace(spilled=True)
    assert under.spill_stands() is True
    under.sink.note_pace(spilled=False)
    assert under.spill_stands() is False
    under.sink.note_pace(spilled=True)
    assert under.spill_stands() is True


@pytest.mark.parametrize("build", _IMPLEMENTATIONS)
def test_writing_the_same_verdict_twice_says_the_same_thing(
    build: Callable[[], PaceSinkUnderTest],
) -> None:
    """Two spilled handoffs in a row are not worse than one, and two good ones are not better."""
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
    """Synchronous by contract, not by accident: the phase calls this inside its persist path.

    An implementation that awaited would put an unrelated collaborator between the deep model's
    stream ending and its reply reaching the store, which is the one hard rule's own sequence.
    """
    assert not inspect.iscoroutinefunction(build().sink.note_pace)


# --- The record: what it says, and for how long -------------------------------------------------


def test_a_spill_rides_a_serving_report_and_names_what_it_costs() -> None:
    """The sentence a person reads, on the surface they already read it on.

    It is deliberately about lost time rather than about the card: a tooltip's reader can act on
    "deep tasks are taking much longer than they should" and cannot act on a decode rate.
    """
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    assert pace.note_on(RESIDENCY_SERVING) == ResidencyReport(
        serving=True, detail=SPILLED_PACE_DETAIL
    )


@pytest.mark.parametrize("report", [RESIDENCY_LOADING, RESIDENCY_DEEP, RESIDENCY_LOST])
def test_a_spill_never_speaks_over_a_swap_that_is_in_flight(report: ResidencyReport) -> None:
    """Mid handoff the seam is already saying what is happening, and to this one.

    A verdict about the *previous* handoff printed under "a deep task is in progress" would be
    read as a verdict about the one running, which is a thing nobody can know yet.
    """
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    assert pace.note_on(report) is report


def test_a_note_stands_for_the_whole_dwell_and_not_a_moment_longer() -> None:
    """The standing rule at its boundary: a fact about one handoff stops describing now.

    Escalation is rare, so waiting for a later handoff to decide it can mean waiting days, and a
    note that never lapsed would still be describing the morning by the evening.
    """
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=DEFAULT_SPILL_DWELL_S)
    pace.note_pace(spilled=True)
    clock.advance(DEFAULT_SPILL_DWELL_S - 1)
    assert pace.note_on(RESIDENCY_SERVING).detail == SPILLED_PACE_DETAIL
    clock.advance(1)
    assert pace.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


def test_a_second_spill_starts_the_dwell_again_from_when_it_happened() -> None:
    """The dwell runs from the handoff, not from the first one this process ever saw."""
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=100.0)
    pace.note_pace(spilled=True)
    clock.advance(99)
    pace.note_pace(spilled=True)
    clock.advance(99)
    assert pace.note_on(RESIDENCY_SERVING).detail == SPILLED_PACE_DETAIL


def test_a_handoff_that_held_its_pace_clears_a_standing_note_at_once() -> None:
    """The other way a note ends, and the only one that is evidence rather than a timeout."""
    clock = _HeldClock()
    pace = HandoffPace(clock, dwell_s=100.0)
    pace.note_pace(spilled=True)
    clock.advance(1)
    pace.note_pace(spilled=False)
    assert pace.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


@pytest.mark.parametrize("dwell_s", [0.0, -1.0])
def test_a_dwell_that_could_never_stand_is_refused(dwell_s: float) -> None:
    """A note that lapses before it is written is a display that cannot work, so it is refused."""
    with pytest.raises(ValueError, match="dwell_s must be > 0"):
        HandoffPace(_HeldClock(), dwell_s=dwell_s)


def test_a_missing_peer_and_a_spilled_handoff_are_both_said() -> None:
    """Two true things with two different remedies: put the tier back, and give the card room.

    Whichever wrote last winning would send an operator to fix one while the other stayed broken,
    so they join, in the order a probe composes them: the standing condition, then the handoff.
    """
    tiers = StandingTiers()
    tiers.mark_missing(_TIER)
    pace = HandoffPace(_HeldClock())
    pace.note_pace(spilled=True)
    composed = pace.note_on(tiers.note_on(RESIDENCY_SERVING))
    assert composed.serving is True
    assert composed.detail == (
        f"{TIERS_MISSING_DETAIL.format(models=_TIER)}; {SPILLED_PACE_DETAIL}"
    )


# --- Through the manager, which is the object a probe actually asks ------------------------------


async def test_a_spilled_handoff_reaches_a_probe_through_the_manager() -> None:
    """The end of the path the entry was filed about: the fact leaves the log for the seam."""
    manager = _manager(ScriptedModelHost(running=[_CORTEX]))
    assert manager.residency() == RESIDENCY_SERVING
    manager.handoff_pace.note_pace(spilled=True)
    assert manager.residency() == ResidencyReport(serving=True, detail=SPILLED_PACE_DETAIL)


async def test_the_pass_that_republishes_a_serving_cortex_does_not_erase_the_note() -> None:
    """The constraint this was built under, asserted rather than trusted.

    The background pass publishes the bare ``RESIDENCY_SERVING`` constant when it finds the cortex
    back, so a detail written **into** the record would last exactly until the next pass. The note
    survives here because it is composed as the report is read, which is the same reason the peer
    record survives one.
    """
    host = ScriptedModelHost(running=[_CORTEX], status_override={_CORTEX: ModelHostState.FAILED})
    manager = _manager(host)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope(_DEEP):
            pass  # pragma: no cover -- a failed swap in never runs the scope's body
    assert manager.residency() == RESIDENCY_LOST
    manager.handoff_pace.note_pace(spilled=True)
    host.set_status(_CORTEX, None)  # the operator put the cortex back through the control API
    await manager.heal_residency()
    assert manager.residency() == ResidencyReport(serving=True, detail=SPILLED_PACE_DETAIL)


async def test_a_probe_reads_a_missing_peer_and_a_spill_off_one_swap() -> None:
    """Both records survive the same swap, and a probe is told both facts in one sentence."""
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
