"""What one attempt at a delegated task produced, and how two of them fold into one.

Split out of ``subagent_attempt.py`` when the total generation cap took that file to the 300-line
cap (ADR-0005 total-cap addendum); the contract is unchanged and ``subagent_attempt`` re-exports
every name here, the ``tool_loop``/``ToolLoopContext`` precedent, so every existing import keeps
resolving.

The seam is which half each side owns. This module is the vocabulary two collaborators share:
``PlacedAttempt`` writes an outcome and ``SubagentRunner`` reads one to decide whether to re-place,
so neither owns it. What stays next to the attempt is the running. The refusal templates every
failure reports as its ``detail`` moved here with it, when carrying a finish reason across the
inference port took the attempt past the line cap (ADR-0005 finish-reason addendum): they are the
``detail`` field's own contents, ``reran_on_cpu`` already folds two of them into a third, and half
a vocabulary living beside the writer and half beside the reader is the split neither collaborator
wanted.

``AttemptFailure`` is the whole reason an outcome is not a bare ``ok`` flag. A backend that did not
answer is worth trying elsewhere; a model that answered outside its grammar, or one still talking
when its deadline arrived, is not. Keying the re-place on ``ok is False`` would spend a second
model load on either of those to be told the same thing.
"""

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

# What the store records about a re-placed run. ADR-0030 asks for the re-place to be recorded in
# the result's detail, and a bare copy of either attempt's reason would hide that two loads were
# spent on one task, which is the whole thing an operator reading a slow spawn wants to see.
_RERAN_AND_ANSWERED = "the GPU attempt failed ({first}); re-ran on the CPU, which answered"
_RERAN_AND_FAILED = "the GPU attempt failed ({first}); the CPU re-run failed too ({second})"

MALFORMED_ENVELOPE_MSG = "subagent produced a malformed constrained reply"

# What the cortex reads when an attempt outran the deadline a delegated run is given (ADR-0005
# total-cap addendum). Phrased like the runner's refusal template rather than like an answer: the
# fragment on the outcome is what the model had said when the clock ran out, mid-sentence by
# construction, so the guidance is to treat the subtask as unanswered and narrow it, never to read
# the fragment as a short result. The bound is named in the message for the same reason the
# admission wait names its own: the reader lands on the knob without going hunting.
GENERATION_DEADLINE_MSG = (
    "the subtask was still generating after {timeout_s:g}s, the whole a delegated run is given, "
    "and was stopped where it stood; a run that reaches this bound is talking rather than "
    "working, so treat the subtask as unanswered and narrow it before delegating it again"
)

# What a bare ``TimeoutError`` from inside the run means, as opposed to the deadline above. A
# socket that timed out or a tool that raised one is the backend failing to answer, which is the
# retryable shape, so it is reported as one rather than as a bound this attempt never reached.
INNER_TIMEOUT_MSG = "the subtask timed out below the delegated run's own deadline"

# What the cortex reads when a completion of the attempt stopped at a token limit rather than at an
# end of its own (ADR-0005 finish-reason addendum), which the backend now says out loud. Phrased
# like the deadline's refusal and for the same reason: the fragment on the outcome stops where the
# count ran out, mid-sentence by construction, so a reader must not take it for a short answer.
# What it does NOT claim is which limit, because the wire cannot tell a request's own cap from the
# server's context window and both cut the same way.
GENERATION_CAP_MSG = (
    "the subtask stopped at a token limit rather than at an answer, so the reply is cut where the "
    "count ran out; a run that reaches such a limit is talking rather than working, so treat the "
    "subtask as unanswered and narrow it before delegating it again"
)

# Appended to the message above only when this deployment set a cap of its own, so the reader lands
# on the knob the way the deadline's message leaves them on one. An unbounded attempt appends
# nothing, for the reason the deadline arm asks ``expired()`` first: quoting a bound that does not
# exist would send the reader after a number nobody chose.
GENERATION_CAP_BOUND = " (this run's own cap is {max_tokens:d} decoded tokens per completion)"


def cap_detail(max_tokens: int | None) -> str:
    """The capped-run refusal, naming this deployment's cap when it set one."""
    if max_tokens is None:
        return GENERATION_CAP_MSG
    return GENERATION_CAP_MSG + GENERATION_CAP_BOUND.format(max_tokens=max_tokens)


class AttemptFailure(Enum):
    """Why an attempt did not answer, or that it did. The retry decision reads exactly this.

    ``INFERENCE`` is the placed backend failing to answer (a dead ``llama-server``, a stream that
    died, a load that could not fit the GPU): the same task on another target may well succeed, so
    this is the only failure a re-place can help. ``MALFORMED`` is the model answering outside its
    constrained grammar, which is a property of the model and the prompt rather than of where it
    ran, so re-placing it would spend a second load to be told the same thing. ``TRUNCATED`` is
    the attempt outrunning its deadline (ADR-0005 total-cap addendum), and it is not re-placed for
    the same reason ``MALFORMED`` is not: a model still talking when its deadline arrived was
    answering, it simply never stopped, and the slower tier is the last place to send it. It is
    also the only one of the three this deployment itself caused, which is why the bound is named
    in the detail: the reader is left with a knob, where the other two leave a server to look at.
    """

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
    """Fold a GPU attempt that did not answer, plus its one CPU re-run, into one outcome.

    The re-run's text and failure win, because it is the attempt that actually ran to an answer
    (or to a second failure); the first attempt's partial text is dropped along with the context
    that produced it. The taint is the **union**: a first attempt that read untrusted content
    before its backend died did consume that content, and under-reporting taint is the one
    direction that costs safety rather than precision (ADR-0013).
    """
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
