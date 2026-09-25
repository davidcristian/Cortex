"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

from cortex_core.images import ImagePart
from cortex_core.tools import ToolCall


def new_turn_id() -> str:
    """A fresh id for one turn of a conversation."""
    return str(uuid4())


class Role(Enum):
    """Who wrote a message: the user, the assistant, the engine (SYSTEM), or a tool result."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# The inference adapter sends content parts only for these roles and a plain string for the
# others, so an image elsewhere would be dropped silently.
_IMAGE_BEARING_ROLES = frozenset({Role.TOOL, Role.USER})


@dataclass(frozen=True, slots=True)
class Message:
    """One immutable entry in a session's history."""

    role: Role
    text: str
    at: datetime
    turn_id: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    images: tuple[ImagePart, ...] = ()

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "Message.at must be timezone-aware"
            raise ValueError(msg)
        if self.images and self.role not in _IMAGE_BEARING_ROLES:
            msg = (
                f"a {self.role.value} message may not have images: pixels are turn-local and "
                "stay with the tool result or user message they arrived on"
            )
            raise ValueError(msg)
