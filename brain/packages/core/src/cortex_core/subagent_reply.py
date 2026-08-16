"""The constrained reply envelope, and what a finished attempt's raw text settles into.

Split out of ``subagent_attempt.py`` when carrying a finish reason across the inference port added
a third thing that could be true of a completed run (ADR-0005 finish-reason addendum) and took that
file past the line cap and the complexity ceiling together. The seam is the one the split before it
drew: ``subagent_attempt`` owns the **running**, meaning the loop, the deadline and the failures a
run can raise on its way; this owns what the text it came back with **means** once the running is
over.

Both directions of the envelope live here, the schema a constrained request asks for and the
unwrapping of the answer, because they are one grammar read twice and a change to either is a
change to both (ADR-0028).

The settling itself is an ordered reading, and the order is the whole of it: a run cut at a token
limit is reported as cut even when the cut landed mid-envelope, because a reply the server stopped
is not a model breaking its grammar, and saying so would send the reader to the model instead of to
the limit. That is the same precedence the deadline arms already keep over this check.
"""

import json

from cortex_core.inference import JsonSchema
from cortex_core.subagent_outcome import (
    MALFORMED_ENVELOPE_MSG,
    AttemptFailure,
    AttemptOutcome,
    cap_detail,
)

__all__ = ["REPLY_ENVELOPE", "settle_reply", "unwrap_envelope"]

# The fixed one-field reply envelope a constrained subagent is decoded into (ADR-0028): there is
# no grammatical position for an appended footer, link, or section, so a jailbroken weak model
# cannot format-launder. The attempt unwraps ``reply`` before reporting its text.
REPLY_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


def unwrap_envelope(text: str) -> str | None:
    """The ``reply`` string from a constrained envelope, or ``None`` if it is malformed.

    A constrained stream should always yield ``{"reply": "..."}``, but a mid-stream failure or a
    weak model that slips the grammar could leave a partial or wrong-shaped payload; that degrades
    to a ``MALFORMED`` outcome rather than reporting raw JSON as the answer. A non-object payload
    or a missing key raises (``TypeError``/``KeyError``), which is caught alongside a decode error.
    """
    try:
        reply = json.loads(text)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return reply if isinstance(reply, str) else None


def settle_reply(
    text: str, *, capped: bool, max_tokens: int | None, constrain: bool, tainted: bool
) -> AttemptOutcome:
    """What an attempt that ran to the end of its loop produced.

    ``capped`` is what the run's ``StopLedger`` saw, meaning at least one of its completions
    stopped at a token limit rather than at an end of its own. It is read **first**, ahead of the
    envelope, because a cut reply lands mid-envelope by construction and ``MALFORMED`` would then
    blame the model for a sentence the server ended. It is the ``TRUNCATED`` the deadline reports,
    in the other unit a runaway is measured in, so the runner declines to re-place it for the same
    reason: a tier that filled its token budget will fill it again, and the slower one is the last
    place to send it.

    ``max_tokens`` is this deployment's own cap, quoted in the refusal only when it set one.
    """
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
