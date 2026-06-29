"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from cortex_core.conversation import Message
from cortex_core.model import ModelLease


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

    ``stream`` yields the assistant reply to ``messages`` as text deltas. ``model``
    is a logical model id (ADR-0004), never a file path. Multimodal input arrives in
    a later slice; failures surface as ``InferenceError``.
    """

    def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]: ...


class ModelManager(Protocol):
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007).

    ``acquire(model)`` returns an async context manager that queues for GPU access and
    yields a ``ModelLease`` for the block's duration; leaving the block releases the GPU
    to the next waiter. v1 holds one resident model and performs no swap, so acquiring any
    other id raises ``ModelUnavailableError``. Failures surface as ``ModelManagerError``.
    """

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class Clock(Protocol):
    """The only time source the core may use; ``now()`` is always timezone-aware."""

    def now(self) -> datetime: ...
