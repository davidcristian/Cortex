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
    """The tools the cortex can call, and the one gateway that runs a call."""

    async def describe_tools(self) -> Sequence[ToolSpec]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolAuditSink(Protocol):
    """Where every dispatched tool call is recorded."""

    async def record(self, invocation: ToolInvocation) -> None: ...


class Confirmer(Protocol):
    """Asks the user, out of band, to confirm a tool call that needs confirmation."""

    async def confirm(self, request: ConfirmationRequest) -> bool: ...
