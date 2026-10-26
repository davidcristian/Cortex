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

# 3,640 tokens at the 1.65 characters a token measured on a pasted log, under a quarter of the
# cortex's 16,384-token context, so a cut result beside a full history window leaves room to reply.
MAX_RESULT_CHARS = 6_000

RESULT_CUT_NOTE = (
    "\n\n(This result is {total:,} characters long and only its first {shown:,} fit in the "
    "context. Ask the tool for a smaller part where it offers one, such as the `head` or `tail` "
    "lines of a file, or tell the person the result is too long to read whole.)"
)


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


def cut_result(content: str) -> tuple[str, str]:
    """``content`` cut to ``MAX_RESULT_CHARS``, at its last line break in the second half when it
    has one, and the note to put after it, empty when nothing was cut."""
    if len(content) <= MAX_RESULT_CHARS:
        return content, ""
    kept = content[:MAX_RESULT_CHARS]
    if (end := kept.rfind("\n")) >= MAX_RESULT_CHARS // 2:
        kept = kept[:end]
    return kept, RESULT_CUT_NOTE.format(total=len(content), shown=len(kept))


def result_message(result: ToolResult, at: datetime, turn_id: str, *, nonce: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers."""
    # The note is the brain's, so it goes after the fence an untrusted result is wrapped in.
    content, note = cut_result(result.content)
    text = content if result.trust is Trust.TRUSTED else wrap_untrusted(content, nonce=nonce)
    return Message(
        role=Role.TOOL,
        text=text + note,
        at=at,
        turn_id=turn_id,
        tool_call_id=result.call_id,
        images=result.images,
    )
