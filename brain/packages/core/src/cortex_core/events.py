"""Domain events emitted while handling a user turn (pure data, no I/O)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A streamed chunk of the assistant reply."""

    text: str


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    """Mid-turn progress for the overlay: a machine-readable ``state`` and a readable ``detail``."""

    state: str
    detail: str


@dataclass(frozen=True, slots=True)
class ToolActivity:
    """An audited tool call the turn is running, sent just before the call is dispatched."""

    tool_name: str
    summary: str


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """How an announced dispatch ended, sent once it resolves."""

    tool_name: str
    ok: bool


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The turn finished and the assistant message was persisted to the store."""

    turn_id: str
    full_text: str


type TurnEvent = TextDelta | StatusUpdate | ToolActivity | ToolOutcome | TurnCompleted
