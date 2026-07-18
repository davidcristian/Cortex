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


# The roles whose messages a session store persists. Anything else is derived per turn and
# dies with it, which is what makes an image on a TOOL message turn-local by construction.
_PERSISTABLE = frozenset({Role.USER, Role.ASSISTANT})


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
        if self.images and self.role in _PERSISTABLE:
            msg = f"a {self.role.value} message may not carry images: pixels are turn-local"
            raise ValueError(msg)
