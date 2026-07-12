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
class ToolActivity:
    """An audited tool call the turn is running (proto ``ToolActivity``), emitted just before
    its dispatch so the overlay's activity chip shows while the tool works (ADR-0009 addendum).
    Both fields are registry-authored: ``tool_name`` is the advertised ``ToolSpec.name`` and
    ``summary`` its description (the loop emits nothing for a call that matched no advertised
    spec). Nothing the model authored, neither the call name nor its arguments, ever rides
    here: a model-authored value would be a display channel the reply-side guardrail (ADR-0015)
    never inspects. Ephemeral like ``StatusUpdate``: never reply text, never persisted.
    """

    tool_name: str
    summary: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The turn finished and the assistant message was persisted to the store."""

    turn_id: str
    full_text: str


type TurnEvent = TextDelta | StatusUpdate | ToolActivity | TurnCompleted
