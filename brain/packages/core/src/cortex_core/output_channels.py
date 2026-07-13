"""One turn's guarded output channels: the reply filter and the thinking status.

The turn engine streams two user-visible surfaces: the reply the user reads and the live
"thinking" status the overlay renders (ADR-0020). Both are model output, so both pass
through the output guardrail (ADR-0015) when one is wired: ``open_output_channels`` opens
the reply's ``OutputFilter`` and a ``ThinkingChannel`` under the SAME policy and user-URL
allowlist, one filter instance each, so the two carry buffers stay independent (a URL is
never joined across the reply/thinking boundary). The thinking surface shipped unguarded
first; scrubbing it closed the display channel a laundered URL in the reasoning trace
would otherwise get once the overlay's chips rendered the detail (ADR-0020 addendum).
Pure like the guardrail itself; all state dies with the turn.
"""

from dataclasses import dataclass

from cortex_core.events import StatusUpdate
from cortex_core.guardrail import OutputFilter, OutputGuardrail, TaintView
from cortex_core.urls import extract_urls

# The StatusUpdate.state a reasoning model's live deliberation is surfaced under (ADR-0020).
# Part of the seam contract: the overlay may switch on it (today it renders any detail).
THINKING_STATE = "thinking"


@dataclass(slots=True)
class ThinkingChannel:
    """The thinking status's own scrubber (ADR-0020 addendum).

    The overlay renders a thinking status's detail, so the reasoning trace is a display
    channel and passes through its own ``OutputFilter`` (``None`` = unguarded), independent
    of the reply's so the two streams' carry buffers never mix. ``feed`` maps one reasoning
    delta to the status to show now (``None`` = wholly carried, empty deltas included).
    One turn's trace is ONE stream: the carry deliberately survives tool steps and reply
    deltas between thinking bursts, so a URL split around a tool call is joined before it
    is matched (per-burst flushing would scrub the fragments separately and neither would
    match a collected identity, letting the full URL cross the seam in consecutive
    statuses). ``release`` drains the scrubbed carry exactly once, at end of stream.
    """

    guard: OutputFilter | None

    def feed(self, text: str) -> StatusUpdate | None:
        """The status event for one reasoning delta, or ``None`` when it is wholly carried."""
        shown = text if self.guard is None else self.guard.feed(text)
        return StatusUpdate(state=THINKING_STATE, detail=shown) if shown else None

    def release(self) -> StatusUpdate | None:
        """The status event draining the scrubbed carry, or ``None`` when nothing is held."""
        held = "" if self.guard is None else self.guard.flush()
        return StatusUpdate(state=THINKING_STATE, detail=held) if held else None


def open_output_channels(
    guardrail: OutputGuardrail | None, taint: TaintView, user_text: str
) -> tuple[OutputFilter | None, ThinkingChannel]:
    """Open one turn's two output channels (the reply filter + the thinking channel).

    Both open over the same live taint view and the same user-URL allowlist (the URLs the
    user's own message carried are theirs to see again on either surface); each gets its own
    filter instance. With no guardrail both channels pass text through unchanged.
    """
    if guardrail is None:
        return None, ThinkingChannel(guard=None)
    allow = extract_urls(user_text)
    return (
        guardrail.open(taint, allow=allow),
        ThinkingChannel(guard=guardrail.open(taint, allow=allow)),
    )
