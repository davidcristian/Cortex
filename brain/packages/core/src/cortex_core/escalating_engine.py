"""One turn, one stream, two models: the wrapper that carries a handoff (ADR-0030 d5/d6)."""

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

    async def handle_turn(self, session_id: str, text: str) -> AsyncGenerator[TurnEvent, None]:
        """Run the cortex phase, then the handoff it asked for, as one turn on one stream."""
        slot = EscalationSlot()
        parts: list[str] = []
        completed: TurnCompleted | None = None
        events = self._make_inner(slot).handle_turn(session_id, text)
        try:
            async for event in events:
                if isinstance(event, TurnCompleted):
                    completed = event
                    continue
                if isinstance(event, TextDelta):
                    parts.append(event.text)
                yield event
        finally:
            # The inner turn is closed deterministically, so a consumer that walks away mid
            # cortex phase leaves no half-suspended loop behind (its own contract: the user
            # message stays, the partial reply is dropped).
            await events.aclose()
        if completed is None:
            # An inner runner that ended without completing was torn down, not finished, so
            # there is no turn to hand off and nothing to complete on its behalf.
            return
        if slot.brief is None:
            yield completed
            return
        handoff = self._conductor.run_handoff(
            slot, session_id=session_id, turn_id=completed.turn_id
        )
        try:
            async for event in handoff:
                if isinstance(event, TextDelta):
                    parts.append(event.text)
                yield event
        finally:
            await handoff.aclose()
        # The one completion, at the true end. Its text is the whole turn's, cortex wrap-up and
        # deep answer alike; each phase already persisted its own message under this turn id.
        yield TurnCompleted(turn_id=completed.turn_id, full_text="".join(parts))
