"""Watching a tier's decode cadence for the one failure a memory reading cannot see (ADR-0030)."""

from dataclasses import dataclass

from cortex_core.inference import DecodeCadence

__all__ = ["MIN_CADENCE_TOKENS", "CadenceReading", "CadenceWatch"]

MIN_CADENCE_TOKENS = 32


@dataclass(frozen=True, slots=True)
class CadenceReading:
    """What a watch has to say once the completions it watched are done."""

    observed: DecodeCadence
    floor: float
    samples: int
    judged: int

    @property
    def collapsed(self) -> bool:
        """Whether the tier never reached the rate its deployment measured for it.

        False whenever no floor was declared, because a watch with nothing to compare against
        cannot find a shortfall; that deployment gets the number and no verdict.
        """
        return self.floor > 0 and self.observed.tokens_per_second < self.floor

    @property
    def shortfall(self) -> float:
        """How far under the floor the tier ran, in tokens per second, zero when it was not."""
        return self.floor - self.observed.tokens_per_second if self.collapsed else 0.0


class CadenceWatch:
    """Collects a tier's reported decode cadences and settles them into one reading."""

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
        """The settled reading, or ``None`` when nothing long enough to judge was ever reported."""
        if self._best is None:
            return None
        return CadenceReading(
            observed=self._best, floor=self._floor, samples=self._samples, judged=self._judged
        )
