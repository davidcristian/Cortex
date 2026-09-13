"""The constrained reply envelope, and what a finished attempt's raw text settles into."""

import json

from cortex_core.inference import JsonSchema
from cortex_core.subagent_outcome import (
    MALFORMED_ENVELOPE_MSG,
    AttemptFailure,
    AttemptOutcome,
    cap_detail,
)

__all__ = [
    "REPLY_ENVELOPE",
    "REPLY_INSTRUCTION",
    "instruct_reply",
    "settle_reply",
    "unwrap_envelope",
]

REPLY_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}

# The schema constrains the next token and describes nothing, so this sentence is the only part
# of the envelope the model reads. Without it the subagent tiers spend the reply field on a plan
# or a copy of the input about one subtask in four.
REPLY_INSTRUCTION = (
    "Your entire response must be the answer itself, not the text you were given. Do not "
    "describe the task, plan an approach, announce what you are about to write, or repeat the "
    "input back."
)


def instruct_reply(instruction: str) -> str:
    """``instruction`` with the constrained path's own sentence appended."""
    return f"{instruction} {REPLY_INSTRUCTION}"


def unwrap_envelope(text: str) -> str | None:
    """The ``reply`` string from a constrained envelope, or ``None`` if it is malformed."""
    try:
        reply = json.loads(text)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return reply if isinstance(reply, str) else None


def settle_reply(
    text: str, *, capped: bool, max_tokens: int | None, constrain: bool, tainted: bool
) -> AttemptOutcome:
    """What an attempt that ran to the end of its loop produced."""
    # ``capped`` is read before the envelope: a cut reply ends mid-envelope, so unwrapping first
    # would report a model that broke its grammar for a reply the server stopped.
    if capped:
        return AttemptOutcome(
            text=text,
            failure=AttemptFailure.TRUNCATED,
            detail=cap_detail(max_tokens),
            tainted=tainted,
        )
    if not constrain:
        return AttemptOutcome(text=text, tainted=tainted)
    reply = unwrap_envelope(text)
    if reply is None:
        return AttemptOutcome(
            text=text,
            failure=AttemptFailure.MALFORMED,
            detail=MALFORMED_ENVELOPE_MSG,
            tainted=tainted,
        )
    return AttemptOutcome(text=reply, tainted=tainted)
