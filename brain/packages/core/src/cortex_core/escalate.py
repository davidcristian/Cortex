"""The ``escalate_to_brain`` built-in tool: request the deep-model handoff (ADR-0030)."""

from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

ESCALATE_TOOL_NAME = "escalate_to_brain"

MAX_BRIEF_CHARS = 4000

# The confirm card's reason for this tool, app-authored fixed text (ADR-0030 decision 1): the
# generic "outbound or irreversible" gate reason would be false here, so the card says what is
# actually being approved. Wired as the default per-tool gate reason at the composition root.
ESCALATE_GATE_REASON = (
    "the deep model will take over this task; loading it claims the whole GPU and the machine "
    "will be busy for several minutes before the assistant answers again"
)

# What the model reads on success. True in order: the gate already ran (this result exists only
# after approval), the request is recorded for the loop boundary, and the model's job now is a
# short wrap-up, not more tool work.
ESCALATION_QUEUED_MSG = (
    "The handoff is approved and queued: the deep model takes over when you finish this reply. "
    "Wrap up now, telling the user in a sentence or two what is being handed off, and do not "
    "call any more tools this turn."
)

_NO_SLOT_MSG = (
    "escalation is not available for this turn, so no handoff was requested. Answer the user "
    "yourself with what you have."
)
_ERR_BRIEF = (
    "escalate_to_brain requires a non-empty 'brief' string stating what the deep model should "
    "do and what has been learned so far"
)
_ERR_BRIEF_TOO_LONG = (
    f"REFUSED: 'brief' may be at most {MAX_BRIEF_CHARS} characters, so no handoff was "
    "requested. Send a shorter brief."
)
_ERR_ALREADY_REQUESTED = (
    "REFUSED: a handoff to the deep model is already requested for this turn, so it was not "
    "requested again. Finish your reply; the deep model takes over when you are done."
)

# Honest about the cost (the spawn spec's measured-trade-off precedent): the swap is disruptive
# and slow, so the description says so plainly instead of selling a free upgrade.
_DESCRIPTION = (
    "Hand the current task over to the deeper reasoning model. Only for tasks that genuinely "
    "exceed what you can do here: the swap unloads this assistant, claims the whole GPU, and "
    "takes several minutes, and the user must approve it first. 'brief' is your handover: "
    "state what the deep model should do and what you have learned so far."
)


class EscalateToBrainTool:
    """Built-in ``escalate_to_brain`` tool: record the turn's handoff request (ADR-0030)."""

    @property
    def spec(self) -> ToolSpec:
        """The gated spec advertised to the cortex; ``gated=True`` is the tool's own flag,
        OR-ed with the composition root's ``CORTEX_TOOLS_GATED`` backstop at dispatch."""
        return ToolSpec(
            name=ESCALATE_TOOL_NAME,
            description=_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "brief": {
                        "type": "string",
                        "maxLength": MAX_BRIEF_CHARS,
                        "description": (
                            "What the deep model should do, and what has been learned so far."
                        ),
                    }
                },
                "required": ["brief"],
            },
            gated=True,
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate the brief and write it into the turn's slot; the swap is not run here."""
        slot = call.stamp.escalation
        if slot is None:
            # No slot was armed for this dispatch: an escalation-less wiring, or a caller with
            # no turn (the ticker). Refusing is honest; nothing could consume a brief here.
            return _refusal(call, _NO_SLOT_MSG)
        brief = call.arguments.get("brief")
        if not isinstance(brief, str) or not brief.strip():
            return _refusal(call, _ERR_BRIEF)
        text = brief.strip()
        if len(text) > MAX_BRIEF_CHARS:
            return _refusal(call, _ERR_BRIEF_TOO_LONG)
        if slot.brief is not None:
            return _refusal(call, _ERR_ALREADY_REQUESTED)
        slot.brief = text
        return ToolResult(call_id=call.id, content=ESCALATION_QUEUED_MSG, trust=Trust.TRUSTED)


def _refusal(call: ToolCall, message: str) -> ToolResult:
    """One refusal shape: our own message, trusted, ``is_error`` so the model recovers."""
    return ToolResult(call_id=call.id, content=message, is_error=True, trust=Trust.TRUSTED)
