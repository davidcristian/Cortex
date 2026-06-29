"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(Enum):
    """Who authored a message: USER/ASSISTANT dialogue, or SYSTEM for engine-injected
    context such as recalled memories (ADR-0008). SYSTEM messages are never persisted to
    a session's history. They are derived fresh per turn and passed only to the model."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Message:
    """One immutable entry in a session's history.

    ``turn_id`` groups the user message with the assistant reply it produced.
    ``at`` must be timezone-aware: session state is externalized and rehydrated
    across processes (the one hard rule), so naive timestamps are ambiguous.
    """

    role: Role
    text: str
    at: datetime
    turn_id: str

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "Message.at must be timezone-aware"
            raise ValueError(msg)
