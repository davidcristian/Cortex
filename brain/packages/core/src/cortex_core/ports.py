"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates."""

from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from cortex_core.conversation import Message
from cortex_core.events import TurnEvent
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.model import ModelLease
from cortex_core.placement import PlacementRequest
from cortex_core.ports_body import BodyGateway
from cortex_core.ports_models import (
    ModelHost,
    PaceSink,
    ResidencyController,
    ResidencyReporter,
)
from cortex_core.ports_placement import SubagentPlacer
from cortex_core.ports_stores import (
    HandoffStore,
    MemoryStore,
    PreferenceStore,
    ScheduleStore,
    SessionStore,
    TaskStore,
)
from cortex_core.ports_tools import (
    Confirmer,
    ToolAuditSink,
    ToolRegistry,
)
from cortex_core.ranking import RecallAudit
from cortex_core.tools import ToolSpec

__all__ = [
    "BodyGateway",
    "Clock",
    "Confirmer",
    "Embedder",
    "HandoffStore",
    "InferenceBackend",
    "MemoryStore",
    "ModelHost",
    "ModelManager",
    "PaceSink",
    "PreferenceStore",
    "RecallAuditSink",
    "ResidencyController",
    "ResidencyReporter",
    "ScheduleStore",
    "SessionStore",
    "Sleeper",
    "SubagentPlacer",
    "SubagentScheduler",
    "TaskStore",
    "ToolAuditSink",
    "ToolRegistry",
    "TurnRunner",
]


class InferenceBackend(Protocol):
    """One stateless streamed completion against a loaded model, with no sessions and no retries."""

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]: ...


class ModelManager(Protocol):
    """Owns the single GPU: leases the resident model and serializes callers."""

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class Embedder(Protocol):
    """Turns text into the vector retrieval ranks on (one stateless call, no I/O state)."""

    async def embed(self, text: str) -> Sequence[float]: ...


class Clock(Protocol):
    """The only time source the core may use; ``now()`` is always timezone-aware."""

    def now(self) -> datetime: ...


class Sleeper(Protocol):
    """The only way core code may wait for wall-clock time to pass."""

    async def sleep(self, seconds: float) -> None: ...


class TurnRunner(Protocol):
    """Runs one user turn as a stream of domain events: what a ``Converse`` stream drives."""

    def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]: ...


class RecallAuditSink(Protocol):
    """Where each recall is recorded, so the hits it returned can be explained later."""

    async def record(self, audit: RecallAudit) -> None: ...


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget."""

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...

    async def drain(self, *, timeout_s: float) -> bool: ...

    def undrain(self) -> None: ...
