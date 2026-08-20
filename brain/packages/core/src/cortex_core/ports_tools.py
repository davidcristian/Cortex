"""The three ports one tool call passes through: what exists, who allows it, what it left."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec

__all__ = [
    "Confirmer",
    "ToolAuditSink",
    "ToolRegistry",
]


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009)."""

    async def describe_tools(self) -> Sequence[ToolSpec]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolAuditSink(Protocol):
    """The audit trail where every dispatched tool call is recorded (AGENTS.md, ADR-0009)."""

    async def record(self, invocation: ToolInvocation) -> None: ...


class Confirmer(Protocol):
    """Answers a request to confirm a gated tool call. Out of band, the human's call (ADR-0013,
    gate table revised by ADR-0022).
    """

    async def confirm(self, request: ConfirmationRequest) -> bool: ...
