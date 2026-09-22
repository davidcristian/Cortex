"""The wrapper that runs a handoff through one turn on one stream."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack

from cortex_core.events import StatusUpdate, TextDelta, TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationSlot
from cortex_core.ports import TurnRunner
from cortex_core.progress import ProgressSink
from cortex_core.swap_conductor import SwapConductor
from cortex_core.waits import SWAPPING, Wait, WaitHold


class EscalatingTurnEngine:
    """A ``TurnRunner`` that can hand its turn to the deep model without ending it."""

    def __init__(
        self,
        make_inner: Callable[[EscalationSlot], TurnRunner],
        conductor: SwapConductor,
        *,
        progress: ProgressSink | None = None,
    ) -> None:
        self._make_inner = make_inner
        self._conductor = conductor
        self._progress = progress

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run the cortex phase, then the handoff it asked for, as one turn on one stream."""
        slot = EscalationSlot()
        parts: list[str] = []
        completed: TurnCompleted | None = None
        events = self._make_inner(slot).handle_turn(session_id, text, turn_id=turn_id)
        try:
            async for event in events:
                if isinstance(event, TurnCompleted):
                    completed = event
                    continue
                if isinstance(event, TextDelta):
                    parts.append(event.text)
                yield event
        finally:
            await events.aclose()
        if completed is None:
            return
        if slot.brief is None:
            yield completed
            return
        handoff = self._conductor.run_handoff(slot, session_id=session_id, turn_id=turn_id)
        async with AsyncExitStack() as held:
            swap: WaitHold | None = None
            try:
                async for event in handoff:
                    if isinstance(event, TextDelta):
                        parts.append(event.text)
                    swap = await self._record_swap(held, swap, event)
                    yield event
            finally:
                await handoff.aclose()
        yield TurnCompleted(turn_id=turn_id, full_text="".join(parts))

    async def _record_swap(
        self, held: AsyncExitStack, swap: WaitHold | None, event: TurnEvent
    ) -> WaitHold | None:
        """Hold a swap status as the turn's wait, quietly, since the stream sends it itself."""
        if not isinstance(event, StatusUpdate) or event.state != SWAPPING or self._progress is None:
            return swap
        wait = Wait(SWAPPING, event.detail)
        if swap is None:
            return await held.enter_async_context(self._progress.hold(wait, announce=False))
        await swap.restate(wait, announce=False)
        return swap
