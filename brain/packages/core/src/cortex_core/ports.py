"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from cortex_core.conversation import Message
from cortex_core.inference import InferenceEvent
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.model import ModelLease
from cortex_core.tools import ToolCall, ToolInvocation, ToolResult, ToolSpec


class SessionStore(Protocol):
    """Source of truth for conversation state; survives model swaps and restarts."""

    async def append(self, session_id: str, message: Message) -> None: ...

    async def history(self, session_id: str) -> Sequence[Message]: ...


class InferenceBackend(Protocol):
    """One stateless streamed completion against a loaded model, with no sessions and no retries."""

    def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]: ...


class ModelManager(Protocol):
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007)."""

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class Embedder(Protocol):
    """Turns text into the vector retrieval ranks on (one stateless call, no I/O state).

    ``embed`` returns the embedding of ``text``; its dimension is fixed by the deployment's
    model (ADR-0008) and the core never assumes a value. Failures surface as ``EmbedderError``.
    """

    async def embed(self, text: str) -> Sequence[float]: ...


class MemoryStore(Protocol):
    """Durable, cross-session memory: append one record, retrieve the top-k by similarity."""

    async def add(self, record: MemoryRecord) -> None: ...

    async def search(self, embedding: Sequence[float], *, k: int) -> Sequence[ScoredMemory]: ...


class Clock(Protocol):
    """The only time source the core may use; ``now()`` is always timezone-aware."""

    def now(self) -> datetime: ...


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009)."""

    async def describe_tools(self) -> Sequence[ToolSpec]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolAuditSink(Protocol):
    """The audit trail where every dispatched tool call is recorded (AGENTS.md, ADR-0009)."""

    async def record(self, invocation: ToolInvocation) -> None: ...
