"""Domain events emitted while handling a user turn (pure data, no I/O).

These are core types; the orchestrator maps them onto the proto's ServerEvent
(``proto/body.proto``) at the seam. The core never imports wire code.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A streamed chunk of the assistant reply."""

    text: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The turn finished and the assistant message was persisted to the store."""

    turn_id: str
    full_text: str


type TurnEvent = TextDelta | TurnCompleted
