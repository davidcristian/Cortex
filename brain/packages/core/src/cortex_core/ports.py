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
    """Source of truth for conversation state; survives model swaps and restarts.

    No conversation state may live anywhere else (AGENTS.md hard rule). A model
    process or the orchestrator may hold a message only for the in-flight turn.
    ``append`` persists one message at the end of a session's history; ``history``
    returns that session's full history in append order (empty when unknown).
    Failures surface as ``SessionStoreError``.
    """

    async def append(self, session_id: str, message: Message) -> None: ...

    async def history(self, session_id: str) -> Sequence[Message]: ...


class InferenceBackend(Protocol):
    """One stateless streamed completion against a loaded model, with no sessions and no retries.

    ``stream`` yields the reply to ``messages`` as ``InferenceEvent``s: ``TextChunk`` deltas
    of assistant text, interleaved with ``ToolCall``s when the model asks to run a tool from
    ``tools`` (native function-calling, ADR-0009). With ``tools`` empty the stream is text
    only, exactly as before. ``model`` is a logical id (ADR-0004), never a file path.
    Multimodal input arrives in a later slice; failures surface as ``InferenceError``.
    """

    def stream(
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]: ...


class ModelManager(Protocol):
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007).

    ``acquire(model)`` returns an async context manager that queues for GPU access and
    yields a ``ModelLease`` for the block's duration; leaving the block releases the GPU
    to the next waiter. v1 holds one resident model and performs no swap, so acquiring any
    other id raises ``ModelUnavailableError``. Failures surface as ``ModelManagerError``.
    """

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class Embedder(Protocol):
    """Turns text into the vector retrieval ranks on (one stateless call, no I/O state).

    ``embed`` returns the embedding of ``text``; its dimension is fixed by the deployment's
    model (ADR-0008) and the core never assumes a value. Failures surface as ``EmbedderError``.
    """

    async def embed(self, text: str) -> Sequence[float]: ...


class MemoryStore(Protocol):
    """Durable, cross-session memory: append one record, retrieve the top-k by similarity.

    ``add`` persists one ``MemoryRecord`` that the caller builds (id, timestamp, embedding),
    so the store only translates, as ``SessionStore.append`` does. ``search`` returns the
    ``k`` records whose embeddings are most similar to ``embedding``, most-similar first,
    ranking over ALL memories (v1 is one global space, ADR-0008). Failures surface as
    ``MemoryStoreError``.
    """

    async def add(self, record: MemoryRecord) -> None: ...

    async def search(self, embedding: Sequence[float], *, k: int) -> Sequence[ScoredMemory]: ...


class Clock(Protocol):
    """The only time source the core may use; ``now()`` is always timezone-aware."""

    def now(self) -> datetime: ...


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009).

    ``describe_tools`` lists what is available (name + JSON-Schema parameters) to advertise
    to the model; ``invoke`` runs one call and returns a ``ToolResult`` whose ``is_error``
    reflects whether the *tool* failed. A dispatch failure (unknown tool, transport) surfaces
    as ``ToolError`` (``ToolNotFoundError`` for an unknown name); the dispatcher, not the
    registry, turns that into an error result the model can read.
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
