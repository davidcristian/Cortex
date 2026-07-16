"""One round of the tool loop: how wide it may be, and the messages it appends.

The fourth bound on the loop, and the only one that bounds the **context** rather than the
reach (ADR-0009 round-cap addendum). ``tool_loop.py`` owns how *long* a loop runs
(``MAX_TOOL_STEPS`` rounds), ``tool_budget.py`` how much of the outside world it may touch,
``tool_salience.py`` whether a call is worth making at all. None of those three bounds how
many calls one round carries, and every call in a round costs an appended ``Role.TOOL``
message whether it ran, was refused as a repeat, or was refused past a closed pool. So a
round of a thousand calls was a thousand messages fed back into the next inference, at a cost
of one dispatch when they were identical, which is why neither the pool nor salience closes
this shape.

A cap on the calls *dispatched* would therefore have bounded nothing here: the refusal is
appended too. The round is capped by **dropping** the calls past ``MAX_CALLS_PER_ROUND``, the
assistant message's own ``tool_calls`` included, so the conversation stays well formed (one
``Role.TOOL`` answer per ``tool_call_id``, the shape the budget addendum's refusals exist to
preserve) and the dropped calls append nothing at all. One slot past the cap is kept and
refused, which is how the model is told the round was truncated rather than left to infer it
from answers that never arrive.

This module also owns the two messages a round appends, because the cap is a cap on exactly
those: how wide the round's footprint in the context may be, and what that footprint is made
of, are one responsibility.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.tools import ToolCall, ToolResult, Trust
from cortex_core.untrusted import wrap_untrusted

# Upper bound on the tool calls one round may dispatch. Sized against the two bounds it sits
# beside: four times the "eight rounds averaging four calls" the dispatch pool was sized for, so
# a legitimate fan-out fits, and half of MAX_TOOL_DISPATCHES, so no single round can spend the
# whole turn's reach in one breath. That second property is the one worth having: a model
# chooses a round's calls before seeing any of that round's results, so a blind burst that could
# exhaust the turn is strictly worse than one that must stop and read halfway. It also makes the
# growth of a loop's context a number rather than a product: at most MAX_TOOL_STEPS * (this + 2)
# messages, where before it was unbounded.
MAX_CALLS_PER_ROUND = 16


@dataclass(frozen=True, slots=True)
class RoundPlan:
    """The calls of one round that reach the context, and whether the model emitted more.

    ``calls`` is what the assistant message records and what the loop iterates: the calls up to
    the cap, plus one overflow slot when the round was truncated. ``overflowed`` says whether
    that last slot is the overflow one, so the loop can refuse it without re-deriving the
    arithmetic. Everything the model emitted past those is gone: not refused, not audited, not
    answered, because a refusal it could read would be the very context growth being bounded.
    """

    calls: tuple[ToolCall, ...]
    overflowed: bool

    def answered(self) -> Iterator[tuple[ToolCall, bool]]:
        """Each call this round answers, paired with whether it is the overflow slot.

        The pairing rather than an index the caller compares: which slot carries the overflow
        is this value's arithmetic, and the loop that consumes it is already at the complexity
        limits that pushed its refusal decision into its own function.
        """
        overflow_at = len(self.calls) - 1 if self.overflowed else None
        for index, call in enumerate(self.calls):
            yield call, index == overflow_at


def plan_round(calls: Sequence[ToolCall]) -> RoundPlan:
    """Which of a round's emitted calls reach the context (ADR-0009 round-cap addendum).

    A round at or under the cap passes through untouched, so the bound is invisible to every
    turn that does ordinary work. Past it the round keeps one call more than the cap: the extra
    is the slot the loop refuses, and keeping it is what turns a silent truncation into one the
    model reads. A truncation it could not observe would leave it re-emitting the dropped calls
    every round until the round bound ran out, which is the failure a cap must not create.
    """
    if len(calls) <= MAX_CALLS_PER_ROUND:
        return RoundPlan(tuple(calls), overflowed=False)
    return RoundPlan(tuple(calls[: MAX_CALLS_PER_ROUND + 1]), overflowed=True)


def call_message(text: str, calls: Sequence[ToolCall], at: datetime, turn_id: str) -> Message:
    """The assistant's tool-calling step, carrying its native ``tool_calls`` for re-inference.

    ``calls`` is the plan's, never the model's raw emission: an assistant message recording a
    call that the round never answers is the malformed conversation the loop's refusals exist
    to avoid, so truncating the round means truncating this too.
    """
    return Message(role=Role.ASSISTANT, text=text, at=at, turn_id=turn_id, tool_calls=tuple(calls))


def result_message(result: ToolResult, at: datetime, turn_id: str, *, nonce: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers.

    UNTRUSTED content is fenced as inert data (ADR-0013); TRUSTED content passes through verbatim.
    """
    text = (
        result.content
        if result.trust is Trust.TRUSTED
        else wrap_untrusted(result.content, nonce=nonce)
    )
    return Message(role=Role.TOOL, text=text, at=at, turn_id=turn_id, tool_call_id=result.call_id)
