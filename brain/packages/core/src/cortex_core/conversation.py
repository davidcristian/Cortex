"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.images import ImagePart
from cortex_core.tools import ToolCall


class Role(Enum):
    """Who authored a message: USER/ASSISTANT dialogue, SYSTEM for engine-injected context such as
    recalled memories (ADR-0008), or TOOL for a tool result fed back to the model (ADR-0009).
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


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
                f"a {self.role.value} message may not carry images: pixels are turn-local and "
                "ride the tool result they arrived on"
            )
            raise ValueError(msg)
