"""The three ports one tool call passes through: what exists, who allows it, what it left.

Split from ``ports.py`` at the line cap, along the seam a dispatch already draws. ``ports.py``
keeps the ports a turn is built out of (inference, the clock, the runner itself); these three
are what ``ToolDispatcher`` holds, and it holds all three: it asks the registry what may be
called and calls it, asks the confirmer about a gated one, and records every outcome to the
audit sink whichever way it went. Nothing else in the tree needs one without the others.

They are stated as three ports rather than one because they answer to three different owners.
The registry is a sidecar's advertisement (ADR-0009), the confirmer is the human, out of band
and never the model (ADR-0013/0022), and the audit sink is the durable record neither of them
can edit. ``ports.py`` re-exports all three, so every existing ``from cortex_core.ports import
...`` and the ``cortex_core`` barrel keep resolving unchanged.
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec

__all__ = [
    "Confirmer",
    "ToolAuditSink",
    "ToolRegistry",
]


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009).

    ``describe_tools`` lists what is available (name + JSON-Schema parameters) to advertise
    to the model; ``invoke`` runs one call and returns a ``ToolResult`` whose ``is_error``
    reflects whether the *tool* failed. A dispatch failure (unknown tool, transport) surfaces
    as ``ToolError`` (``ToolNotFoundError`` for an unknown name); the dispatcher, not the
    registry, turns that into an error result the model can read.

    A listing is read at the call and never cached. ``AggregateToolRegistry`` and
    ``UngatedToolRegistry`` resolve ownership and gating by walking ``describe_tools`` on every
    invoke, so an implementation answering from a set it cached at construction would route to a
    tool its server has since dropped, and would advertise a gated one as ungated.

    What an unknown name looks like differs between implementations, and only the safety half is
    common. The core's own registries hold their whole set and raise ``ToolNotFoundError``. A
    remote one can only report what its server says, and an MCP server answers an unknown tool
    with an error result, so ``McpToolRegistry`` returns ``is_error`` there rather than raising.
    Every implementation must ensure that a name it does not serve never comes back as a
    successful result; a caller that needs the distinction resolves ownership by a live walk
    first, which is exactly what the aggregate does before it routes.
    """

    async def describe_tools(self) -> Sequence[ToolSpec]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolAuditSink(Protocol):
    """The audit trail where every dispatched tool call is recorded (AGENTS.md, ADR-0009).

    ``record`` persists one ``ToolInvocation``; it is awaited on every dispatch, success or
    failure, so no tool call is ever unaudited. Adapters log structured lines; the fake keeps
    them in memory for assertions.
    """

    async def record(self, invocation: ToolInvocation) -> None: ...


class Confirmer(Protocol):
    """Answers a request to confirm a gated tool call, out of band (ADR-0013, ADR-0022).

    ``confirm`` returns ``True`` to allow an irreversible/outbound action, ``False`` to block it.
    ADR-0022 revised the gate table. The dispatcher consults it for a gated call on an untainted
    turn (a tainted turn's gated call is denied outright, and the confirmer is never asked). The
    decision is the user's, reached out
    of band (the overlay), never the model's. A jailbroken model cannot forge it. The real
    adapter is the orchestrator's ``SeamConfirmer``, round-tripping the overlay's approval card
    over the ``Converse`` stream; a missing confirmer denies (fail-closed).
    """

    async def confirm(self, request: ConfirmationRequest) -> bool: ...
