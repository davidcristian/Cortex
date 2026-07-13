"""One turn's guarded output channels: the reply filter and the thinking status."""

from dataclasses import dataclass

from cortex_core.events import StatusUpdate
from cortex_core.guardrail import OutputFilter, OutputGuardrail, TaintView
from cortex_core.urls import extract_urls

THINKING_STATE = "thinking"


@dataclass(slots=True)
class ThinkingChannel:
    """The output filter for the thinking status, separate from the reply's own."""

    guard: OutputFilter | None

    def feed(self, text: str) -> StatusUpdate | None:
        """The status event for one piece of reasoning, or ``None`` while the filter holds it."""
        shown = text if self.guard is None else self.guard.feed(text)
        return StatusUpdate(state=THINKING_STATE, detail=shown) if shown else None

    def release(self) -> StatusUpdate | None:
        """The status event for whatever the filter held back, or ``None`` when it held nothing."""
        held = "" if self.guard is None else self.guard.flush()
        return StatusUpdate(state=THINKING_STATE, detail=held) if held else None


def open_output_channels(
    guardrail: OutputGuardrail | None, taint: TaintView, user_text: str
) -> tuple[OutputFilter | None, ThinkingChannel]:
    """Open one turn's two output channels (the reply filter + the thinking channel)."""
    if guardrail is None:
        return None, ThinkingChannel(guard=None)
    allow = extract_urls(user_text)
    return (
        guardrail.open(taint, allow=allow),
        ThinkingChannel(guard=guardrail.open(taint, allow=allow)),
    )
