"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Protocol

from cortex_core.body import VolumeState
from cortex_core.conversation import Message
from cortex_core.inference import InferenceEvent, JsonSchema
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.model import ModelLease
from cortex_core.placement import Placement, PlacementRequest
from cortex_core.schedule import FireOutcome, ScheduleClaim, ScheduledItem
from cortex_core.schedule_transitions import ScheduleEdit
from cortex_core.sessions import SessionSummary
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec


class SessionStore(Protocol):
    """Source of truth for conversation state; survives model swaps and restarts."""

    async def append(self, session_id: str, message: Message) -> None: ...

    async def history(self, session_id: str) -> Sequence[Message]: ...

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]: ...

    async def set_title(self, session_id: str, title: str) -> None: ...


class InferenceBackend(Protocol):
    """One stateless streamed completion against a loaded model, with no sessions and no retries."""

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
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


class MemoryStore(Protocol):
    """Durable, cross-session memory: append one record, retrieve the top-k by similarity."""

    async def add(self, record: MemoryRecord) -> None: ...

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]: ...


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


class Confirmer(Protocol):
    """Answers a request to confirm a gated tool call. Out of band, the human's call (ADR-0013,
    gate table revised by ADR-0022).
    """

    async def confirm(self, request: ConfirmationRequest) -> bool: ...


class TaskStore(Protocol):
    """Hot store for in-flight subagent tasks and their results (Redis; ADR-0010)."""

    async def put_task(self, task: SubagentTask) -> None: ...

    async def get_task(self, task_id: str) -> SubagentTask | None: ...

    async def put_result(self, result: SubagentResult) -> None: ...

    async def get_result(self, task_id: str) -> SubagentResult | None: ...


class ScheduleStore(Protocol):
    """Durable schedules with a fenced claim→finish protocol (ADR-0025)."""

    async def add(self, item: ScheduledItem) -> None: ...

    async def get(self, item_id: str) -> ScheduledItem | None: ...

    async def list_active(self) -> Sequence[ScheduledItem]: ...

    async def cancel(self, item_id: str) -> bool: ...

    async def snooze(self, item_id: str, *, until: datetime) -> bool: ...

    async def edit(self, item_id: str, edit: ScheduleEdit) -> bool: ...

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]: ...

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool: ...

    async def release(self, claim: ScheduleClaim) -> bool: ...

    async def deliverable(self) -> Sequence[ScheduledItem]: ...

    async def ack(self, item_id: str) -> bool: ...


class BodyGateway(Protocol):
    """Calls the host body to read or change an OS setting over the brain→body seam (ADR-0023)."""

    async def get_volume(self) -> VolumeState: ...

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState: ...

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool: ...


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget. Concurrency, not the GPU (ADR-0012)."""

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...
