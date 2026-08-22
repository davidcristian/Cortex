"""Tool domain values: what a tool is, a call to one, its result, and the audit record."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from cortex_core.images import ImagePart
from cortex_core.progress import ProgressSink
from cortex_core.provenance import Provenance
from cortex_core.tool_budget import DispatchBudget

if TYPE_CHECKING:
    from cortex_core.handoff import EscalationSlot


class Trust(Enum):
    """The provenance of a tool result's content: is it data or instructions?

    Every default in this module is ``UNTRUSTED``, so content reaching the model without an
    explicit stamp is framed as data rather than obeyed.
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool advertised to the model: its name, a one-line purpose, and its JSON-Schema args."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    # Marks an outbound or irreversible action, which needs the user's confirmation and is
    # refused outright once the turn has read untrusted content.
    gated: bool = False


@dataclass(frozen=True, slots=True)
class TurnStamp:
    """What the dispatching turn hands the call, stamped on at dispatch time."""

    session_id: str = ""
    turn_id: str = ""
    task_id: str = ""
    item_id: str = ""
    tainted: bool = False
    sources: tuple[Provenance, ...] = ()
    budget: DispatchBudget | None = field(default=None, compare=False)
    progress: ProgressSink | None = field(default=None, compare=False)
    escalation: "EscalationSlot | None" = field(default=None, compare=False)


UNSTAMPED = TurnStamp()


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to run one tool: the model's chosen ``name`` and ``arguments``."""

    id: str
    name: str
    arguments: Mapping[str, Any]
    # Never the model's to set: the dispatcher overwrites it at dispatch time with the calling
    # turn's own stamp.
    stamp: TurnStamp = UNSTAMPED


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of one ``ToolCall``: ``content`` fed back to the model, ``is_error`` set when the
    tool (or its dispatch) failed.
    """

    call_id: str
    content: str
    is_error: bool = False
    trust: Trust = Trust.UNTRUSTED
    source: Provenance | None = None
    images: tuple[ImagePart, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """One line of the audit trail: every dispatched call is recorded, success or failure."""

    name: str
    arguments: Mapping[str, Any]
    ok: bool
    detail: str
    at: datetime
    trust: Trust = Trust.UNTRUSTED
    call_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    task_id: str = ""
    item_id: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "ToolInvocation.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """A request for out-of-band user confirmation of a tool call."""

    tool_name: str
    arguments: Mapping[str, Any]
    reason: str
