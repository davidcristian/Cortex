"""Decode-cadence policy: whether a tier ran at the rate its deployment measured for it."""

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

# Below this many decoded tokens a reported rate describes the server start rather than the
# card: a spilled and a healthy deep-model rate differ by only about 10 tokens per second.
MIN_CADENCE_TOKENS = 32


@dataclass(frozen=True, slots=True)
class CadenceReading:
    """The result of one watch, once the completions it observed are done."""

    observed: DecodeCadence
    floor: float
    samples: int
    judged: int

    @property
    def verdict(self) -> bool | None:
        """Whether the tier ran below the floor, or ``None`` when no floor was set."""
        if self.floor <= 0:
            return None
        return self.observed.tokens_per_second < self.floor

    @property
    def collapsed(self) -> bool:
        """Whether the tier never reached the rate its deployment measured for it."""
        return self.verdict is True

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


@dataclass(frozen=True, slots=True)
class CadenceTerms:
    """What one deep phase's watch runs under: the floor to compare against, and where to report."""

    floor_tps: float = 0.0
    sink: PaceSink | None = None


NO_CADENCE_TERMS = CadenceTerms()
