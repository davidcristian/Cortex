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
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool advertised to the model: its name, a one-line purpose, and its JSON-Schema args.

    ``parameters`` is the JSON Schema the model fills to call the tool, passed through to the
    model verbatim and never interpreted by the core.
    """

    name: str
    description: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to run one tool: the model's chosen ``name`` and ``arguments``.

    ``id`` correlates this call with its ``ToolResult`` across the tool loop; the model (or
    the loop, for a fake backend) assigns it.
    """

    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of one ``ToolCall``: ``content`` fed back to the model, ``is_error`` set
    when the tool (or its dispatch) failed. The model is told, so it can recover."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """One line of the audit trail: every dispatched call is recorded, success or failure.

    ``ok`` is the negation of the result's ``is_error``; ``detail`` is the result content or
    the error message; ``at`` must be timezone-aware (the audit outlives the process).
    """

    name: str
    arguments: Mapping[str, Any]
    ok: bool
    detail: str
    at: datetime

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "ToolInvocation.at must be timezone-aware"
            raise ValueError(msg)
