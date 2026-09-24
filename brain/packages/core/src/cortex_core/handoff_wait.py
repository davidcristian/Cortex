"""A turn's wait behind another turn's handoff, announced wherever the turn meets it."""

from collections.abc import AsyncGenerator, AsyncIterator, Sequence

from cortex_core.conversation import Message
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.ports import InferenceBackend, ResidencyQueue
from cortex_core.progress import ProgressSink, hold_wait
from cortex_core.swap_notes import HANDOFF_AHEAD_DETAIL, SWAPPING_STATE
from cortex_core.tools import ToolSpec
from cortex_core.waits import Wait

HANDOFF_AHEAD = Wait(SWAPPING_STATE, HANDOFF_AHEAD_DETAIL)


async def wait_out_handoff(
    queue: ResidencyQueue, progress: ProgressSink | None, model: str
) -> None:
    """Hold an announced ``swapping`` wait while another model's handoff keeps ``model`` waiting."""
    # A status is a turn event, so the body's first gap ends here instead of running on through
    # a wait whose heartbeats it counts as this turn's own silence.
    while queue.blocks(model):
        async with hold_wait(progress, HANDOFF_AHEAD):
            await queue.await_scope_end(model)


class HandoffAheadBackend:
    """An ``InferenceBackend`` that announces and waits out another handoff before each stream."""

    def __init__(
        self, inner: InferenceBackend, queue: ResidencyQueue, progress: ProgressSink | None
    ) -> None:
        self._inner = inner
        self._queue = queue
        self._progress = progress

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Wait out any handoff ahead of ``model``, then stream from the wrapped backend."""
        await wait_out_handoff(self._queue, self._progress, model)
        # Nothing is awaited between the check above and the lease the stream below takes, so no
        # scope can begin in between and leave the lease's own wait unannounced.
        events = self._inner.stream(model, messages, tools=tools, schema=schema, bounds=bounds)
        try:
            async for event in events:
                yield event
        finally:
            if isinstance(events, AsyncGenerator):
                await events.aclose()
