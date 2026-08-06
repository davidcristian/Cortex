"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates."""

from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from cortex_core.body import ScreenCapture, VolumeState
from cortex_core.conversation import Message
from cortex_core.events import TurnEvent
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.model import ModelLease
from cortex_core.placement import Placement, PlacementRequest
from cortex_core.ports_models import ModelHost, ResidencyController, ResidencyReporter
from cortex_core.ports_stores import (
    HandoffStore,
    MemoryStore,
    PreferenceStore,
    ScheduleStore,
    SessionStore,
    TaskStore,
)
from cortex_core.ranking import RecallAudit
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec

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
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007)."""

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class SubagentPlacer(Protocol):
    """Fit-tests a subagent onto the GPU under the VRAM soft cap, else CPU (ADR-0012)."""

    def place(self, request: PlacementRequest) -> Placement: ...

    def release(self, placement: Placement) -> None: ...


class Embedder(Protocol):
    """Turns text into the vector retrieval ranks on (one stateless call, no I/O state).

    ``embed`` returns the embedding of ``text``; its dimension is fixed by the deployment's
    model (ADR-0008) and the core never assumes a value. Failures surface as ``EmbedderError``.
    """

    async def embed(self, text: str) -> Sequence[float]: ...


class Clock(Protocol):
    """The only time source the core may use; ``now()`` is always timezone-aware."""

    def now(self) -> datetime: ...


class Sleeper(Protocol):
    """The only way core code may wait for wall-clock time to pass (ADR-0030 decision 4)."""

    async def sleep(self, seconds: float) -> None: ...


class TurnRunner(Protocol):
    """Runs one user turn as a stream of domain events: what a ``Converse`` stream drives."""

    def handle_turn(self, session_id: str, text: str) -> AsyncGenerator[TurnEvent, None]: ...


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009)."""

    async def describe_tools(self) -> Sequence[ToolSpec]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolAuditSink(Protocol):
    """The audit trail where every dispatched tool call is recorded (AGENTS.md, ADR-0009)."""

    async def record(self, invocation: ToolInvocation) -> None: ...


class RecallAuditSink(Protocol):
    """The trail that answers "why did recall return these?" (ADR-0038 decision 5)."""

    async def record(self, audit: RecallAudit) -> None: ...


class Confirmer(Protocol):
    """Answers a request to confirm a gated tool call. Out of band, the human's call (ADR-0013,
    gate table revised by ADR-0022).
    """

    async def confirm(self, request: ConfirmationRequest) -> bool: ...


class BodyGateway(Protocol):
    """Calls the host body to read or change an OS setting over the brain→body seam (ADR-0023)."""

    async def get_volume(self) -> VolumeState: ...

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState: ...

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool: ...

    async def capture_screen(self, *, max_edge: int = 0, max_bytes: int = 0) -> ScreenCapture: ...


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget. Concurrency, not the GPU (ADR-0012)."""

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...

    async def drain(self, *, timeout_s: float) -> bool: ...

    def undrain(self) -> None: ...
