"""The wrapper that carries a handoff through one turn on one stream (ADR-0030 d5/d6).

The handoff happens inside the escalating turn, on the stream the user already holds. This
wrapper is what makes that true, and it is deliberately thin: per turn it builds the
``EscalationSlot``, constructs the inner ``TurnEngine`` around it (engines are stateless, so
per-turn construction is free), passes every event through, and then, only if the cortex
actually asked to escalate, runs the conductor's phase and completes the turn once at its true
end.

Why the inner ``TurnCompleted`` is suppressed and re-emitted: the turn is not over when the
cortex stops talking, and a consumer that saw a completion would stop reading, start the next
queued turn, and mark the exchange finished while the deep model was still loading. So exactly
one ``TurnCompleted`` crosses, at the true end, carrying the whole turn's text (the cortex's
wrap-up plus whatever the deep model added), while the cortex's own reply is already persisted
as its own message by the inner engine.

When no escalation was requested the wrapper is transparent: the inner event stream is passed
through unchanged, completion included, so a deployment with escalation enabled behaves exactly
as one without it until the model actually asks for the deep tier.
"""

from collections.abc import AsyncGenerator, Callable

from cortex_core.events import TextDelta, TurnCompleted, TurnEvent
from cortex_core.handoff import EscalationSlot
from cortex_core.ports import TurnRunner
from cortex_core.swap_conductor import SwapConductor


class EscalatingTurnEngine:
    """A ``TurnRunner`` that can hand its turn to the deep model without ending it.

    ``make_inner`` builds this turn's engine around the slot it is given; the composition root
    supplies it, so the wrapper is not written against an engine's constructor. The wrapper holds
    no state between turns: the slot, the inner engine, and the accumulated text all die with the
    turn.
    """

    def __init__(
        self, make_inner: Callable[[EscalationSlot], TurnRunner], conductor: SwapConductor
    ) -> None:
        self._make_inner = make_inner
        self._conductor = conductor

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run the cortex phase, then the handoff it asked for, as one turn on one stream.

        The id is this wrapper's from the first statement rather than read off the inner
        completion it used to wait for, which is what lets the handoff be claimed under the
        turn's own name even on a path where the cortex never finishes.
        """
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
        handoff = self._conductor.run_handoff(slot, session_id=session_id, turn_id=turn_id)
        try:
            async for event in handoff:
                if isinstance(event, TextDelta):
                    parts.append(event.text)
                yield event
        finally:
            await handoff.aclose()
        # The one completion, at the true end. Its text is the whole turn's, cortex wrap-up and
        # deep answer alike; each phase already persisted its own message under this turn id.
        yield TurnCompleted(turn_id=turn_id, full_text="".join(parts))
