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


# Only a tool message may have images: the inference adapter sends content parts for a tool
# message and a plain string for every other role, so an image elsewhere is dropped silently.
_IMAGE_BEARING_ROLE = Role.TOOL


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
        if self.images and self.role is not _IMAGE_BEARING_ROLE:
            msg = (
                f"a {self.role.value} message may not have images: pixels are turn-local and "
                "stay with the tool result they arrived on"
            )
            raise ValueError(msg)
