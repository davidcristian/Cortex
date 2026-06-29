"""Conversation domain: who said what, when, in which turn (pure data, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

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
    """

    role: Role
    text: str
    at: datetime
    turn_id: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "Message.at must be timezone-aware"
            raise ValueError(msg)
