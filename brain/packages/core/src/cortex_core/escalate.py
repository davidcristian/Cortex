"""The ``escalate_to_brain`` built-in tool: request the deep-model handoff (ADR-0030).

The cortex decides mid-turn that a task is out of its depth and calls this like any tool; the
``brief`` argument is its handover, the statement of what the deep model should do and what has
been learned so far. The spec is **gated**, which buys both existing protections at zero new
mechanism (ADR-0030 decision 1): on an untainted turn the user approves the disruption via the
ADR-0022 confirm card (whose per-tool reason says what is true about the swap), and on a
tainted turn the dispatcher hard-denies the call with the confirmer never consulted
(``dispatch.py``), so injected content can never force an eviction.

The tool holds no per-stream state: it reads the turn's ``EscalationSlot`` off the dispatch
``TurnStamp`` per call (the ``spawn_subagents`` progress-sink discipline), writes only
``slot.brief``, and returns. The swap itself happens at the loop boundary, after this turn's
generator finishes: the conductor (a later handoff slice) snapshots the armed slot into a
``READY`` ``HandoffRecord`` and runs the swap, so the success result tells the model to wrap
up rather than pretending anything already swapped. The brief is model-authored text in the
conversation's own trust domain; it is bounded here before it can enter the handoff record,
and it rides WITH the record's serialized taint ledger, never instead of it.

Deferred with the vision slice (ADR-0029, designed but not landed): the opaque-turn refusal.
``Message`` carries no pixels today, so there is nothing to refuse yet; when the vision slice
lands image-bearing messages and the ``opaque`` bit, this tool refuses to escalate a turn
carrying screen-capture pixels (ADR-0030 decision 1), recorded in
``docs/refinements/untrusted-content.md``.
"""

from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

ESCALATE_TOOL_NAME = "escalate_to_brain"

# Upper bound on the brief, the one model-authored string this tool persists into the handoff
# record. Roughly a page of handover text: enough to state the task and everything learned so
# far, small enough that an unbounded model string cannot bloat the hot-store record. Refused,
# never truncated (the spawn batch-cap precedent): a silently cut-off handover would prime the
# deep model with an ask that looks complete and is not.
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
        """Validate the brief and write it into the turn's slot; the swap is not run here.

        The slot rides the dispatch ``TurnStamp`` per call, never instance state, so this one
        shared tool serves every stream without a per-stream field to leak across turns. Every
        refusal is our own message (``Trust.TRUSTED``) the model can act on, never a raise.
        """
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
