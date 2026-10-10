"""One turn's guarded output channels: the reply filter and the thinking status."""

from dataclasses import dataclass, field

from cortex_core.events import StatusUpdate
from cortex_core.guardrail import OutputFilter, OutputGuardrail, TaintView
from cortex_core.urls import extract_urls
from cortex_core.waits import THINKING as THINKING_STATE

ROUND_BREAK = "\n\n"


@dataclass(slots=True)
class ThinkingChannel:
    """The output filter for the thinking status, separate from the reply's own."""

    guard: OutputFilter | None
    _said: bool = field(default=False, init=False)
    _new_round: bool = field(default=False, init=False)

    def next_round(self) -> None:
        """Start the next shown reasoning with ``ROUND_BREAK``, once something was shown before."""
        self._new_round = self._said

    def feed(self, text: str) -> StatusUpdate | None:
        """The status event for one piece of reasoning, or ``None`` while the filter holds it."""
        return self._status(text if self.guard is None else self.guard.feed(text))

    def release(self) -> StatusUpdate | None:
        """The status event for whatever the filter held back, or ``None`` when it held nothing."""
        return self._status("" if self.guard is None else self.guard.flush())

    def _status(self, shown: str) -> StatusUpdate | None:
        # The break goes in after the filter, so a URL steered across a tool step is still
        # read as one stream; text the filter held over the step shows after the break.
        if not shown:
            return None
        if self._new_round:
            shown = ROUND_BREAK + shown
        self._said, self._new_round = True, False
        return StatusUpdate(state=THINKING_STATE, detail=shown)


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
