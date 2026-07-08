"""Tool domain values: what a tool is, a call to one, its result, and the audit record."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class Trust(Enum):
    """The provenance of a tool result's content (ADR-0013): is it data or instructions?"""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool advertised to the model: its name, a one-line purpose, and its JSON-Schema args."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    gated: bool = False


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to run one tool: the model's chosen ``name`` and ``arguments``."""

    id: str
    name: str
    arguments: Mapping[str, Any]
    tainted: bool = False


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of one ``ToolCall``: ``content`` fed back to the model, ``is_error`` set
    when the tool (or its dispatch) failed. The model is told, so it can recover.
    """

    call_id: str
    content: str
    is_error: bool = False
    trust: Trust = Trust.UNTRUSTED


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """One line of the audit trail: every dispatched call is recorded, success or failure."""

    name: str
    arguments: Mapping[str, Any]
    ok: bool
    detail: str
    at: datetime
    trust: Trust = Trust.UNTRUSTED

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "ToolInvocation.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """A request for out-of-band user confirmation of a gated tool call (ADR-0013/0022)."""

    tool_name: str
    arguments: Mapping[str, Any]
    reason: str
