"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
The five state-store ports (session, memory, task, schedule, handoff) live in
``ports_stores.py`` and the two model-lifecycle ports (``ModelHost``, ``ResidencyController``)
in ``ports_models.py``; both sets are re-exported here, so
``from cortex_core.ports import SessionStore`` keeps resolving.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from cortex_core.body import VolumeState
from cortex_core.conversation import Message
from cortex_core.inference import InferenceEvent, JsonSchema
from cortex_core.model import ModelLease
from cortex_core.placement import Placement, PlacementRequest
from cortex_core.ports_models import ModelHost, ResidencyController
from cortex_core.ports_stores import (
    HandoffStore,
    MemoryStore,
    ScheduleStore,
    SessionStore,
    TaskStore,
)
from cortex_core.tools import ConfirmationRequest, ToolCall, ToolInvocation, ToolResult, ToolSpec

# The five state-store ports live in ``ports_stores.py`` and the two model-lifecycle ports in
# ``ports_models.py`` (line-cap splits); the explicit export list re-exports them alongside the
# ports defined here, so every existing ``from cortex_core.ports import ...`` and the
# ``cortex_core`` barrel keep resolving unchanged.
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
    "ResidencyController",
    "ScheduleStore",
    "SessionStore",
    "Sleeper",
    "SubagentPlacer",
    "SubagentScheduler",
    "TaskStore",
    "ToolAuditSink",
    "ToolRegistry",
]


class InferenceBackend(Protocol):
    """One stateless streamed completion against a loaded model, with no sessions and no retries.

    ``stream`` yields the reply to ``messages`` as ``InferenceEvent``s: ``TextChunk`` deltas
    of assistant text, interleaved with ``ToolCall``s when the model asks to run a tool from
    ``tools`` (native function-calling, ADR-0009). With ``tools`` empty the stream is text
    only, exactly as before. ``model`` is a logical id (ADR-0004), never a file path.
    ``schema`` (ADR-0028), when set, constrains decoding so every emitted token conforms to
    that JSON Schema; ``None`` (the default, every caller but a constrained tool-less subagent)
    leaves output unconstrained. Multimodal input arrives in a later slice; failures surface
    as ``InferenceError``.
    """

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]: ...


class ModelManager(Protocol):
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007).

    ``acquire(model)`` returns an async context manager that queues for GPU access and
    yields a ``ModelLease`` for the block's duration; leaving the block releases the GPU
    to the next waiter. v1 holds one resident model and performs no swap, so acquiring any
    other id raises ``ModelUnavailableError``. Failures surface as ``ModelManagerError``.
    Subagent VRAM placement is a separate concern behind ``SubagentPlacer`` (ADR-0012), so
    this port (and Slice 11's swap that reuses ``acquire``) stays unchanged.
    """

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


class SubagentPlacer(Protocol):
    """Fit-tests a subagent onto the GPU under the VRAM soft cap, else CPU (ADR-0012).

    ``place(request)`` decides where one subagent runs: it reserves ``request.vram_gb`` and returns
    a GPU ``Placement`` when it fits the live headroom (``soft_cap - cortex_reservation - placed``),
    else a CPU ``Placement`` reserving nothing (the whole model on one target, never a straddle).
    ``release(placement)`` returns the reserved VRAM to the ledger. Both are sync (a fit-test, not
    a wait) and must pair exactly once, which ``SubagentRunner`` does in a ``finally``. It
    is the GPU/VRAM contract, kept separate from the ``ModelManager``'s exclusive lease and the
    ``SubagentScheduler``'s CPU/RAM budget; the three compose at the runner (ADR-0010 decision 6).
    """

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
    """The only way core code may wait for wall-clock time to pass (ADR-0030 decision 4).

    ``Clock`` answers what time it is, which bounds a wait but cannot perform one, and the core
    may not reach for ``asyncio.sleep`` itself: a poll loop that did would make every test of it
    a real-time test. So waiting is a port, exactly as it already is on the body side (the Rust
    ``Sleeper`` trait behind the transport's retry backoff). The real adapter is
    ``AsyncioSleeper``; the twin records what was asked for and yields the loop instead of
    waiting, which is what keeps the swap suite free of wall-clock sleeps.

    First consumer: the swap's readiness gate, which polls ``ModelHost.status`` between waits.
    """

    async def sleep(self, seconds: float) -> None: ...


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


class Confirmer(Protocol):
    """Answers a request to confirm a gated tool call. Out of band, the human's call (ADR-0013,
    gate table revised by ADR-0022).

    ``confirm`` returns ``True`` to allow an irreversible/outbound action, ``False`` to block it.
    The dispatcher consults it for a gated call on an **untainted** turn (a tainted turn's gated
    call is denied outright, the confirmer never asked). The decision is the user's, reached out
    of band (the overlay), never the model's. A jailbroken model cannot forge it. The real
    adapter is the orchestrator's ``SeamConfirmer``, round-tripping the overlay's approval card
    over the ``Converse`` stream; a missing confirmer denies (fail-closed).
    """

    async def confirm(self, request: ConfirmationRequest) -> bool: ...


class BodyGateway(Protocol):
    """Calls the host body to read or change an OS setting over the brain→body seam (ADR-0023).

    The first bidirectional direction of the seam: the brain is the client of the body's
    ``BodyService``. ``get_volume`` reports the host's current audio state; ``set_volume``
    applies a change (``level`` clamped to [0.0, 1.0], ``mute``, or both, with a ``None`` field
    left untouched) and reports the state after. Both return a domain ``VolumeState``; no wire
    type crosses this boundary. ``notify`` (ADR-0025) shows a native notification (the push
    half of reminder delivery), returning whether the body displayed it (``False`` or an error
    leaves the reminder deliverable for the pull path; ``tainted`` marks attacker-influenced
    text so the body can badge it and must render it inert). Failures (the body unreachable,
    an OS error, an unimplemented capability) surface as ``BodyGatewayError``, which callers
    turn into recoverable outcomes. The port is deliberately abstract so the connectivity
    fallback (a body-initiated tunnel, ADR-0001 Q3) is a later adapter, not a seam change.
    """

    async def get_volume(self) -> VolumeState: ...

    async def set_volume(
        self, *, level: float | None = None, mute: bool | None = None
    ) -> VolumeState: ...

    async def notify(
        self, *, title: str, body: str, reminder_id: str, tainted: bool = False
    ) -> bool: ...


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget. Concurrency, not the GPU (ADR-0012).

    ``admit(request)`` returns an async context manager that yields once the request's ``cpus``/
    ``memory_gb`` fit the remaining budget (summed admitted ``cpus`` ≤ cpu target AND summed
    ``memory_gb`` ≤ memory target) and releases both on exit; over budget, callers wait (depth-1
    delegation guarantees no spawn waits on another spawn, so this cannot deadlock). A charge larger
    than the whole budget can never be admitted, so it raises ``SubagentAdmissionError`` rather than
    waiting forever; any implementation owes that refusal, since ``SubagentRunner`` degrades exactly
    this error to an ``ok=False`` result instead of letting an exception kill the turn (ADR-0012
    admission-wall addendum). The budget binds nothing it did not admit (no ``.wslconfig``/parent
    cgroup, the user's constraint), which is the sense in which it is *soft*; it is distinct from
    the ``ModelManager``'s GPU lease and the ``SubagentPlacer``'s VRAM ledger. The three compose at
    the runner (ADR-0010 decision 6, ADR-0012).

    ``drain(timeout_s=...)`` quiesces the pool for a model handoff (ADR-0030 decision 4, the
    additive method ADR-0012 deferred): it stops admission at once and waits, bounded by
    ``timeout_s`` seconds, for in-flight admissions to release. From the call until ``undrain``,
    every ``admit`` refuses with the same typed ``SubagentAdmissionError`` instead of queuing
    (a brain-phase spawn queued against its own drain would deadlock the turn against its own
    swap), and a caller already waiting on a full budget is woken so it refuses rather than
    sleeps through the swap. True means the pool drained clean; False means the bound elapsed
    with work still in flight, and nothing was killed (v1 never kills a subagent mid-stream),
    so the swap conductor must abort the handoff before evicting anything. ``undrain()``
    reverses the window, resuming normal admission; the conductor owes it in a ``finally``
    (swap-back and aborted handoff alike), so admission always resumes. Both are idempotent.
    """

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...

    async def drain(self, *, timeout_s: float) -> bool: ...

    def undrain(self) -> None: ...
