"""ProgressSink: a side channel for progress a suspended turn cannot yield itself."""

from contextlib import AbstractAsyncContextManager, nullcontext
from typing import Protocol

from cortex_core.events import StatusUpdate, ToolActivity
from cortex_core.waits import Wait, WaitHold

type ProgressEvent = ToolActivity | StatusUpdate


class ProgressSink(Protocol):
    """Emit ephemeral progress onto the turn's stream, and record what the turn waits on."""

    async def emit(self, event: ProgressEvent) -> None: ...

    def hold(
        self, wait: Wait, *, announce: bool = True
    ) -> AbstractAsyncContextManager[WaitHold]: ...


def hold_wait(
    progress: ProgressSink | None, wait: Wait
) -> AbstractAsyncContextManager[WaitHold | None]:
    """Hold ``wait`` on ``progress`` for a block, or do nothing when there is no sink."""
    if progress is None:
        return nullcontext()
    return progress.hold(wait)
