"""What one attempt at a delegated task produced, and how two of them fold into one."""

from dataclasses import dataclass
from enum import Enum

# What the store records about a re-placed run. ADR-0030 asks for the re-place to be recorded in
# the result's detail, and a bare copy of either attempt's reason would hide that two loads were
# spent on one task, which is the whole thing an operator reading a slow spawn wants to see.
_RERAN_AND_ANSWERED = "the GPU attempt failed ({first}); re-ran on the CPU, which answered"
_RERAN_AND_FAILED = "the GPU attempt failed ({first}); the CPU re-run failed too ({second})"


class AttemptFailure(Enum):
    """Why an attempt did not answer, or that it did. The retry decision reads exactly this."""

    NONE = "none"
    INFERENCE = "inference"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    """What one attempt produced: its text, why it failed if it did, and whether it read taint."""

    text: str
    failure: AttemptFailure = AttemptFailure.NONE
    detail: str = ""
    tainted: bool = False

    @property
    def ok(self) -> bool:
        """Whether this attempt answered, which is what the persisted result's ``ok`` becomes."""
        return self.failure is AttemptFailure.NONE


def reran_on_cpu(first: AttemptOutcome, retried: AttemptOutcome) -> AttemptOutcome:
    """Fold a GPU attempt that did not answer, plus its one CPU re-run, into one outcome."""
    detail = (
        _RERAN_AND_ANSWERED.format(first=first.detail)
        if retried.ok
        else _RERAN_AND_FAILED.format(first=first.detail, second=retried.detail)
    )
    return AttemptOutcome(
        text=retried.text,
        failure=retried.failure,
        detail=detail,
        tainted=first.tainted or retried.tainted,
    )
