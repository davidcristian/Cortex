"""One round of the tool loop: how wide it may be, and the messages it appends."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.tools import ToolCall, ToolResult, Trust
from cortex_core.untrusted import wrap_untrusted

# Half of ``MAX_TOOL_DISPATCHES``, so one round cannot spend a whole turn's reach before the
# model has read any of that round's results.
MAX_CALLS_PER_ROUND = 16


@dataclass(frozen=True, slots=True)
class RoundPlan:
    """The calls of one round that reach the context, and whether the model emitted more."""

    calls: tuple[ToolCall, ...]
    overflowed: bool

    def answered(self) -> Iterator[tuple[ToolCall, bool]]:
        """Each call this round answers, paired with whether it is the overflow slot."""
        overflow_at = len(self.calls) - 1 if self.overflowed else None
        for index, call in enumerate(self.calls):
            yield call, index == overflow_at


def plan_round(calls: Sequence[ToolCall]) -> RoundPlan:
    """Which of a round's emitted calls reach the context."""
    # One call past the cap is kept and later refused, which is how the model learns the round
    # was cut. Everything beyond that is dropped without being refused, audited or answered,
    # because a refusal it could read would itself be the context growth this bounds.
    if len(calls) <= MAX_CALLS_PER_ROUND:
        return RoundPlan(tuple(calls), overflowed=False)
    return RoundPlan(tuple(calls[: MAX_CALLS_PER_ROUND + 1]), overflowed=True)


def call_message(text: str, calls: Sequence[ToolCall], at: datetime, turn_id: str) -> Message:
    """The assistant's tool-calling step, with its native ``tool_calls`` for re-inference."""
    return Message(role=Role.ASSISTANT, text=text, at=at, turn_id=turn_id, tool_calls=tuple(calls))


def result_message(result: ToolResult, at: datetime, turn_id: str, *, nonce: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers."""
    text = (
        result.content
        if result.trust is Trust.TRUSTED
        else wrap_untrusted(result.content, nonce=nonce)
    )
    return Message(
        role=Role.TOOL,
        text=text,
        at=at,
        turn_id=turn_id,
        tool_call_id=result.call_id,
        images=result.images,
    )
