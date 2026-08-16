"""What one attempt at a delegated task produced, and how two of them fold into one."""

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "GENERATION_CAP_BOUND",
    "GENERATION_CAP_MSG",
    "GENERATION_DEADLINE_MSG",
    "INNER_TIMEOUT_MSG",
    "MALFORMED_ENVELOPE_MSG",
    "AttemptFailure",
    "AttemptOutcome",
    "cap_detail",
    "reran_on_cpu",
]

_RERAN_AND_ANSWERED = "the GPU attempt failed ({first}); re-ran on the CPU, which answered"
_RERAN_AND_FAILED = "the GPU attempt failed ({first}); the CPU re-run failed too ({second})"

MALFORMED_ENVELOPE_MSG = "subagent produced a malformed constrained reply"

GENERATION_DEADLINE_MSG = (
    "the subtask was still generating after {timeout_s:g}s, the whole a delegated run is given, "
    "and was stopped where it stood; a run that reaches this bound is talking rather than "
    "working, so treat the subtask as unanswered and narrow it before delegating it again"
)

INNER_TIMEOUT_MSG = "the subtask timed out below the delegated run's own deadline"

GENERATION_CAP_MSG = (
    "the subtask stopped at a token limit rather than at an answer, so the reply is cut where the "
    "count ran out; a run that reaches such a limit is talking rather than working, so treat the "
    "subtask as unanswered and narrow it before delegating it again"
)

GENERATION_CAP_BOUND = " (this run's own cap is {max_tokens:d} decoded tokens per completion)"


def cap_detail(max_tokens: int | None) -> str:
    """The capped-run refusal, naming this deployment's cap when it set one."""
    if max_tokens is None:
        return GENERATION_CAP_MSG
    return GENERATION_CAP_MSG + GENERATION_CAP_BOUND.format(max_tokens=max_tokens)


class AttemptFailure(Enum):
    """Why an attempt did not answer, or that it did."""

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
