"""ProgressSink: a side channel for progress a suspended turn cannot yield itself."""

from typing import Protocol

from cortex_core.events import StatusUpdate, ToolActivity

type ProgressEvent = ToolActivity | StatusUpdate


class ProgressSink(Protocol):
    """Emit one ephemeral progress event onto the turn's stream from outside its generator."""

    async def emit(self, event: ProgressEvent) -> None: ...
