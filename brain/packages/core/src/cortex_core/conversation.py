"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(Enum):
    """Who authored a message in a session."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class Message:
    """One immutable entry in a session's history."""

    role: Role
    text: str
    at: datetime
    turn_id: str

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "Message.at must be timezone-aware"
            raise ValueError(msg)
