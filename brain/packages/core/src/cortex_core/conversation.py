"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from cortex_core.images import ImagePart
from cortex_core.tools import ToolCall


class Role(Enum):
    """Who authored a message: USER/ASSISTANT dialogue, SYSTEM for engine-injected context
    such as recalled memories (ADR-0008), or TOOL for a tool result fed back to the model
    (ADR-0009). SYSTEM and the in-turn TOOL / tool-call messages are never persisted to a
    session's history. They are derived per turn and passed only to the model."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# The roles whose messages a session store persists. Anything else is derived per turn and
# dies with it, which is what makes an image on a TOOL message turn-local by construction.
_PERSISTABLE = frozenset({Role.USER, Role.ASSISTANT})


@dataclass(frozen=True, slots=True)
class Message:
    """One immutable entry in a session's history.

    ``turn_id`` groups the user message with the assistant reply it produced.
    ``at`` must be timezone-aware: session state is externalized and rehydrated
    across processes (the one hard rule), so naive timestamps are ambiguous.

    The tool fields carry the native function-calling structure through the in-turn tool
    loop (ADR-0009): ``tool_calls`` is set on an ASSISTANT message that asked to run tools,
    ``tool_call_id`` on a TOOL message carrying one call's result. Both default empty for
    ordinary dialogue; v1 does not persist tool-bearing messages (the loop is turn-local),
    so the session store never serializes these.

    ``images`` carries pixels a tool returned (ADR-0029), and **only a non-persistable role may
    carry them**. That is an invariant, not a convention: an image lives on the ``Role.TOOL``
    message in the tool loop's working list and dies with the turn, exactly like the security
    preamble and a recalled-memory SYSTEM message. Constructing an image-bearing USER or
    ASSISTANT message raises here, before any store is asked to refuse it, so the rule holds
    even for code paths that never touch a store.
    """

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
