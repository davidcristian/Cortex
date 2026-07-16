"""ProgressSink: a side channel for ephemeral progress a suspended turn cannot yield (ADR-0010)."""

from typing import Protocol

from cortex_core.events import StatusUpdate, ToolActivity

# The two ephemeral event kinds a sink carries: an audited tool step surfaced as activity, and a
# brain-authored progress line as status. Never a ``TextDelta`` (progress is not reply text) nor a
# ``TurnCompleted`` (a turn ends through its own generator, not this side channel).
type ProgressEvent = ToolActivity | StatusUpdate


class ProgressSink(Protocol):
    """Emit one ephemeral progress event onto the turn's stream from outside its generator."""

    async def emit(self, event: ProgressEvent) -> None: ...
