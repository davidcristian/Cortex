"""Decode-cadence policy: whether a tier ran at the rate its deployment measured for it (ADR-0030).

Pure policy over the ``DecodeCadence`` events a backend reports, with no I/O and no logging of its
own. It is the only instrument for a handoff that overcommitted the card, because such a handoff
succeeds: both tiers report ``ready``, the fit check has already passed on a declared cost that was
too low or on room the desktop took during the load, and free memory afterwards reads the same as a
genuine fit. Throughput is what differs, roughly halved.

Two rules follow, both argued in ADR-0030's spill-watch addendum. A completion shorter than
``MIN_CADENCE_TOKENS`` is collected and never judged, since its rate is dominated by whatever the
server was doing when it started, and a watch that saw only such samples has no reading at all,
which is a third answer and not a pass. The fastest qualifying sample decides, because a spill is a
ceiling that holds for every completion while the overcommit lasts, so a card that was momentarily
busy during one round of a tool loop cannot alone produce a verdict.

The floor is the deployment's own measurement of its own card, the twin of
``ResidencyPlan.brain_vram_mib`` and just as unknowable from inside a container; zero, the default,
means none was declared, and then the watch reports what it saw and judges nothing. It travels with
the ``PaceSink`` that receives the verdict, the pair being ``CadenceTerms``. What is done with the
verdict belongs to the caller, and ``residency_pace.py`` is the one that answers a probe with it.
"""

from dataclasses import dataclass

from cortex_core.inference import DecodeCadence
from cortex_core.ports import PaceSink

__all__ = [
    "MIN_CADENCE_TOKENS",
    "NO_CADENCE_TERMS",
    "CadenceReading",
    "CadenceTerms",
    "CadenceWatch",
]

# Below this many decoded tokens a completion's reported rate says more about the server's start
# than about the card. Chosen against the measured contrast rather than by feel: the spilled and
# healthy deep-model rates differ by about 10 tok/s, so a sample has to span enough tokens for
# that gap to survive the noise of one prompt's first token. Thirty two is roughly a sentence of
# reply, which every deep-phase answer clears and a bare tool-call round does not.
MIN_CADENCE_TOKENS = 32


@dataclass(frozen=True, slots=True)
class CadenceReading:
    """What one watch settled on once the completions it watched are done.

    ``observed`` is the fastest qualifying sample, so it is the best case the tier managed;
    ``floor`` is what the deployment declared, zero meaning it declared nothing. ``samples`` and
    ``judged`` are how many cadences arrived at all and how many were long enough to count, which
    is what makes a reading legible in a log: "no reading" reads differently when nothing was
    reported than when everything reported was too short.
    """

    observed: DecodeCadence
    floor: float
    samples: int
    judged: int

    @property
    def verdict(self) -> bool | None:
        """Whether the tier spilled, or ``None`` when there was nothing to judge it against.

        A deployment that declared no floor gets the number and no judgement at all, which is a
        different answer from a tier that was found to be fine. The difference matters wherever a
        verdict is published rather than logged, since a note that stands until something
        contradicts it must not be cleared by a deployment that declared no floor
        (``residency_pace.py``).
        """
        if self.floor <= 0:
            return None
        return self.observed.tokens_per_second < self.floor

    @property
    def collapsed(self) -> bool:
        """Whether the tier never reached the rate its deployment measured for it.

        False whenever no floor was declared, since there is then nothing to compare the rate
        against; that deployment gets the number and no verdict.
        """
        return self.verdict is True

    @property
    def shortfall(self) -> float:
        """How far under the floor the tier ran, in tokens per second, zero when it was not."""
        return self.floor - self.observed.tokens_per_second if self.collapsed else 0.0


class CadenceWatch:
    """Collects a tier's reported decode cadences and settles them into one reading.

    One watch per handoff, not per completion: a deep phase runs a whole tool loop, so several
    completions arrive under one swap and the question is about the tier across all of them.
    Stateful and deliberately not stored anywhere (the one hard rule): a watch is scratch for the
    duration of one phase, and its conclusion is reported rather than persisted.
    """

    def __init__(self, floor: float = 0.0, *, min_tokens: int = MIN_CADENCE_TOKENS) -> None:
        if floor < 0:
            msg = f"CadenceWatch floor must be >= 0, got {floor}"
            raise ValueError(msg)
        if min_tokens < 1:
            msg = f"CadenceWatch min_tokens must be >= 1, got {min_tokens}"
            raise ValueError(msg)
        self._floor = floor
        self._min_tokens = min_tokens
        self._samples = 0
        self._judged = 0
        self._best: DecodeCadence | None = None

    def observe(self, sample: DecodeCadence) -> None:
        """Take one completion's reported cadence, keeping it only if it is long enough to judge."""
        self._samples += 1
        if sample.tokens < self._min_tokens:
            return
        self._judged += 1
        if self._best is None or sample.tokens_per_second > self._best.tokens_per_second:
            self._best = sample

    def reading(self) -> CadenceReading | None:
        """The settled reading, or ``None`` when nothing long enough to judge was ever reported.

        ``None`` is not a pass and must never be logged as one: it is what a backend whose engine
        reports no timings looks like, and it is also what a phase that failed before it decoded
        anything looks like.
        """
        if self._best is None:
            return None
        return CadenceReading(
            observed=self._best, floor=self._floor, samples=self._samples, judged=self._judged
        )


@dataclass(frozen=True, slots=True)
class CadenceTerms:
    """The terms one deep phase's watch runs under: the floor to judge against, and where to report.

    The two travel together because the dependency ceiling is a design rule (ruff.toml) and because
    neither is much use alone: a floor with no sink ends in a log line, and a sink with no floor
    carries no verdict.

    ``floor_tps`` is the deployment's own measurement of its own card, zero (the default, and
    every deployment that has not measured one) meaning the rate is reported and nothing is
    judged. ``sink`` is where the verdict goes beyond the log (``PaceSink``, implemented by the
    residency record the seam reads), ``None`` covering every caller that watches without
    publishing: a test, and any deployment wired before the note existed.
    """

    floor_tps: float = 0.0
    sink: PaceSink | None = None


# The default a phase is built with when its caller says nothing about cadence: no floor to judge
# against and no sink to report to. Shared because it is frozen, as the seam's empty port bundle is.
NO_CADENCE_TERMS = CadenceTerms()
