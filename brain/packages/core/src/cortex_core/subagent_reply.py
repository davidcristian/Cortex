"""The constrained reply envelope, and what a finished attempt's raw text settles into.

Split out of ``subagent_attempt.py`` when carrying a finish reason across the inference port added
a third thing that could be true of a completed run (ADR-0005 finish-reason addendum) and took that
file past the line cap and the complexity ceiling together. The seam is the one the split before it
drew: ``subagent_attempt`` owns the running, meaning the loop, the deadline and the failures a run
can raise on its way, and this module owns what the text it came back with means once the running
is over.

Both directions of the envelope live here, the schema a constrained request asks for and the
unwrapping of the answer, because they are one grammar read twice and a change to either is a
change to both (ADR-0028). The sentence the constrained path appends to its subtask lives here for
the same reason and is the third side of the same contract: it states in words what the grammar can
only enforce, and on this engine those words are the only half the model ever reads (ADR-0028
instruction addendum).

The settling is an ordered reading, and the order matters: a run cut at a token limit is reported
as cut even when the cut landed mid-envelope, because a reply the server stopped is not a model
breaking its grammar, and reporting it as malformed would send the reader to the model instead of
to the limit. That is the same precedence the deadline arms already keep over this check.
"""

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

# What the envelope cannot say, said in the one channel that reaches the model (ADR-0028
# instruction addendum). A schema on this engine constrains the next token and never describes a
# contract: the same pick renders a byte-identical prompt with the envelope and without it, so
# ``reply`` is a name the grammar builder reads and the model never sees. Left to itself under that
# grammar the tier answers a deliberation-inviting subtask one time in four by spending the field
# on a plan, and this sentence is what recovers the answer.
#
# It names the answer rather than a genre, because a subtask here is a summarization, an extraction
# or a lookup and the wording must not tune itself to one of them. It is appended rather than
# prefixed so it is the last thing said, which is the position that survives an instruction the
# cortex composed from content it read.
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
    stopped at a token limit rather than at an end of its own. It is read first, ahead of the
    envelope, because a cut reply lands mid-envelope by construction and ``MALFORMED`` would then
    report a model error for a sentence the server ended. It is the ``TRUNCATED`` the deadline
    reports, in the other unit a runaway is measured in, so the runner declines to re-place it for
    the same reason: a tier that filled its token budget will fill it again, and the slower tier is
    the last place to send it.

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
