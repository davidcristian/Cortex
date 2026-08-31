"""The spill watch: the rules a decode rate has to meet before it is judged.

The instrument this covers exists because an overcommitted card does not fail. It serves the
answer, reports ``ready``, and reads on ``nvidia-smi`` exactly like a card that fitted; the only
difference measured on the 24 GB card was throughput, 14.80 to 17.29 tok/s spilled against 25.07
to 33.28 with the card to itself. These tests cover the rules that keep a slow number from being
reported as a spill, and a spill from being reported as healthy.

Mutations proving these tests can fail (each was applied on its own, then restored):
- dropping the ``min_tokens`` guard in ``CadenceWatch.observe`` fails
  ``test_a_sample_too_short_to_judge_is_counted_and_never_judged``;
- keeping the slowest sample instead of the fastest fails
  ``test_the_fastest_qualifying_sample_decides``;
- letting ``collapsed`` compare against a floor of zero fails
  ``test_an_undeclared_floor_reports_and_judges_nothing``;
- returning a reading rather than ``None`` when nothing qualified fails
  ``test_a_watch_that_saw_nothing_judgeable_has_no_reading_at_all``.
"""

import pytest

from cortex_core import MIN_CADENCE_TOKENS, CadenceWatch, DecodeCadence

_FLOOR = 22.0


def _sample(tps: float, tokens: int = 64) -> DecodeCadence:
    return DecodeCadence(tokens_per_second=tps, tokens=tokens)


def test_a_rate_under_the_declared_floor_is_a_collapse() -> None:
    watch = CadenceWatch(_FLOOR)
    watch.observe(_sample(16.4))
    reading = watch.reading()
    assert reading is not None
    assert reading.collapsed
    assert reading.observed.tokens_per_second == 16.4
    assert reading.shortfall == pytest.approx(5.6)


def test_a_rate_at_or_above_the_floor_is_not() -> None:
    watch = CadenceWatch(_FLOOR)
    watch.observe(_sample(_FLOOR))
    reading = watch.reading()
    assert reading is not None
    assert not reading.collapsed
    assert reading.shortfall == 0.0


def test_an_undeclared_floor_reports_and_judges_nothing() -> None:
    """A floor of zero means the deployment never measured a rate, so the reading carries the
    number and no verdict."""
    watch = CadenceWatch()
    watch.observe(_sample(0.4))
    reading = watch.reading()
    assert reading is not None
    assert reading.observed.tokens_per_second == 0.4
    assert not reading.collapsed
    assert reading.floor == 0.0


def test_a_sample_too_short_to_judge_is_counted_and_never_judged() -> None:
    """A sample below ``MIN_CADENCE_TOKENS`` counts toward ``samples`` and is never judged,
    because a handful of tokens measures the server's start rather than the card."""
    watch = CadenceWatch(_FLOOR)
    watch.observe(_sample(2.0, tokens=MIN_CADENCE_TOKENS - 1))
    assert watch.reading() is None
    watch.observe(_sample(30.0, tokens=MIN_CADENCE_TOKENS))
    reading = watch.reading()
    assert reading is not None
    assert reading.samples == 2
    assert reading.judged == 1
    assert not reading.collapsed


def test_the_fastest_qualifying_sample_decides() -> None:
    """The fastest qualifying sample is the one judged, because a spill holds a ceiling for the
    whole phase and one slow round on its own is not evidence of it."""
    watch = CadenceWatch(_FLOOR)
    watch.observe(_sample(31.0))
    watch.observe(_sample(9.0))
    watch.observe(_sample(28.0))
    reading = watch.reading()
    assert reading is not None
    assert reading.observed.tokens_per_second == 31.0
    assert reading.judged == 3
    assert not reading.collapsed


def test_a_tier_that_never_once_reached_its_floor_is_what_a_spill_looks_like() -> None:
    watch = CadenceWatch(_FLOOR)
    for tps in (14.8, 17.29, 15.5):
        watch.observe(_sample(tps))
    reading = watch.reading()
    assert reading is not None
    assert reading.collapsed
    assert reading.observed.tokens_per_second == 17.29


def test_a_watch_that_saw_nothing_judgeable_has_no_reading_at_all() -> None:
    """A watch with no qualifying sample returns ``None``, which a caller can tell apart from a
    reading that cleared the floor."""
    assert CadenceWatch(_FLOOR).reading() is None


@pytest.mark.parametrize(
    ("floor", "min_tokens"),
    [pytest.param(-0.1, 8, id="negative-floor"), pytest.param(1.0, 0, id="zero-min-tokens")],
)
def test_a_watch_refuses_arguments_that_could_not_judge_anything(
    floor: float, min_tokens: int
) -> None:
    with pytest.raises(ValueError, match="must be >="):
        CadenceWatch(floor, min_tokens=min_tokens)


@pytest.mark.parametrize(
    ("tps", "tokens"),
    [pytest.param(-1.0, 8, id="negative-rate"), pytest.param(1.0, -8, id="negative-tokens")],
)
def test_a_cadence_refuses_a_figure_no_server_could_mean(tps: float, tokens: int) -> None:
    with pytest.raises(ValueError, match="must be >="):
        DecodeCadence(tokens_per_second=tps, tokens=tokens)
