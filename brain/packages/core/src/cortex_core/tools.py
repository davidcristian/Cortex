"""Tool domain values: what a tool is, a call to one, its result, and the audit record.

Pure data, no I/O and no ``ports`` import. That lets ``ports.py`` depend on these without a
cycle, exactly as ``memory.py`` is depended on. ``arguments``/``parameters`` carry arbitrary
JSON (a tool's schema and a model's call args are open-shaped), so ``Any`` here is the
justified kind: the boundary is genuinely dynamic and the value is round-tripped, never
introspected by the core.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class Trust(Enum):
    """The provenance of a tool result's content (ADR-0013): is it data or instructions?

    ``UNTRUSTED`` content comes from a third party (file contents, email bodies, later web
    pages and screen captures) and must be framed as inert data the model never obeys.
    ``TRUSTED`` content is system-generated (a built-in's status string). The distinction is
    binary because the boundary only ever acts on that one question. The default everywhere is
    ``UNTRUSTED`` (fail-closed): content that reaches the model without an explicit trust stamp
    is framed as hostile, never silently trusted.
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool advertised to the model: its name, a one-line purpose, and its JSON-Schema args.

    ``parameters`` is the JSON Schema the model fills to call the tool, passed through to the
    model verbatim and never interpreted by the core. ``gated`` marks an irreversible/outbound
    action (email-write, later OS actions) that requires explicit confirmation once the turn
    has read untrusted content (ADR-0013); no tool sets it today (all reads are read-only).
    """

    name: str
    description: str
    parameters: Mapping[str, Any]
    gated: bool = False


@dataclass(frozen=True, slots=True)
class TurnStamp:
    """The dispatching turn's provenance, stamped onto every call at dispatch time (ADR-0027).

    ``session_id`` is the originating chat (``""`` when the dispatch has none: a subagent
    run, or an unattributed caller); ``tainted`` whether the turn had read untrusted content
    at dispatch time. One frozen value rather than parallel keywords, so future provenance
    facts (source URI, sender; the ADR-0013/0019 deferrals) join this object and every call
    site rides along unchanged. A field joins only with a consumer.
    """

    session_id: str = ""
    tainted: bool = False


# The unattributed default stamp: no originating session, no taint. A named constant
# (not a call in a default) so signatures can default to it under the lint gate.
UNSTAMPED = TurnStamp()


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to run one tool: the model's chosen ``name`` and ``arguments``.

    ``id`` correlates this call with its ``ToolResult`` across the tool loop; the model (or
    the loop, for a fake backend) assigns it. ``stamp`` is never the model's to set: the
    dispatcher overwrites it at dispatch time with the calling turn's ``TurnStamp``
    (ADR-0018/0027), so a built-in that spawns further work (``spawn_subagents``, the
    schedule tools) can propagate provenance. The stamp is transient (the loop persists the
    unstamped calls) and it never feeds the ADR-0013 gate, which uses the dispatcher's
    explicit argument.
    """

    id: str
    name: str
    arguments: Mapping[str, Any]
    stamp: TurnStamp = UNSTAMPED


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of one ``ToolCall``: ``content`` fed back to the model, ``is_error`` set
    when the tool (or its dispatch) failed. The model is told, so it can recover.

    ``trust`` is the provenance of ``content`` (ADR-0013), defaulting ``UNTRUSTED`` so any
    result reaching the loop without an explicit stamp is framed as data. A generic registry
    (MCP, the in-memory twin) leaves the default; only a built-in returning system-generated
    bytes stamps ``TRUSTED``.
    """

    call_id: str
    content: str
    is_error: bool = False
    trust: Trust = Trust.UNTRUSTED


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """One line of the audit trail: every dispatched call is recorded, success or failure.

    ``ok`` is the negation of the result's ``is_error``; ``detail`` is the result content or
    the error message; ``trust`` records whether the call returned untrusted content (the
    provenance trail, ADR-0013); ``at`` must be timezone-aware (the audit outlives the process).
    """

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
    """A request for out-of-band user confirmation of a gated tool call (ADR-0013/0022).

    Built by the dispatcher when a ``gated`` tool is called on an **untainted** turn (a tainted
    turn's gated call is denied outright, never confirmed per ADR-0022): ``tool_name``/``arguments``
    name the action and ``reason`` says why confirmation is required, so the overlay can show the
    user what they are approving. The ``Confirmer`` port answers it; the model never does, since
    confirmation is the human's, out of band.
    """

    tool_name: str
    arguments: Mapping[str, Any]
    reason: str
