"""The wrapper that runs a handoff through one turn on one stream."""

from collections.abc import AsyncGenerator, Callable

from cortex_core.events import TextDelta, TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationSlot
from cortex_core.ports import TurnRunner
from cortex_core.swap_conductor import SwapConductor


class EscalatingTurnEngine:
    """A ``TurnRunner`` that can hand its turn to the deep model without ending it."""

    def __init__(
        self, make_inner: Callable[[EscalationSlot], TurnRunner], conductor: SwapConductor
    ) -> None:
        self._make_inner = make_inner
        self._conductor = conductor

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
        try:
            async for event in handoff:
                if isinstance(event, TextDelta):
                    parts.append(event.text)
                yield event
        finally:
            await handoff.aclose()
        yield TurnCompleted(turn_id=turn_id, full_text="".join(parts))
