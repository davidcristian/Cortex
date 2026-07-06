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
class StatusUpdate:
    """Mid-turn progress for the overlay to show (proto ``StatusUpdate``): a machine-readable
    ``state`` and human-readable ``detail``. Ephemeral (never persisted, not part of the reply).
    First use (ADR-0020) is the cortex's reasoning trace (``state="thinking"``); the general
    shape (model swap, queue position) is reused by later slices.
    """

    state: str
    detail: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The turn finished and the assistant message was persisted to the store."""

    turn_id: str
    full_text: str


type TurnEvent = TextDelta | StatusUpdate | TurnCompleted
