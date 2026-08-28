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

# The fixed one-field reply envelope a constrained subagent is decoded into (ADR-0028): there is
# no grammatical position for an appended footer, link, or section, so a jailbroken weak model
# cannot format-launder. The attempt unwraps ``reply`` before reporting its text.
REPLY_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}

REPLY_INSTRUCTION = (
    "Your entire response must be the answer itself. Do not describe the task, plan an "
    "approach, or announce what you are about to write."
)


def instruct_reply(instruction: str) -> str:
    """``instruction`` with the constrained path's own sentence appended.

    One function rather than an f-string at the call site, so the harness that measures this can
    strip exactly what the runner adds and read the counterfactual against the shipped path.
    """
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
    if capped:
        return AttemptOutcome(
            text=text,
            failure=AttemptFailure.TRUNCATED,
            detail=cap_detail(max_tokens),
            tainted=tainted,
        )
    if not constrain:
        return AttemptOutcome(text=text, tainted=tainted)
    # Unwrap the envelope so the cortex sees an answer, never raw JSON (ADR-0028).
    reply = unwrap_envelope(text)
    if reply is None:
        return AttemptOutcome(
            text=text,
            failure=AttemptFailure.MALFORMED,
            detail=MALFORMED_ENVELOPE_MSG,
            tainted=tainted,
        )
    return AttemptOutcome(text=reply, tainted=tainted)
