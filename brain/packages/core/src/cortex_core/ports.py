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
    """Source of truth for conversation state; survives model swaps and restarts.

    No conversation state may live anywhere else (AGENTS.md hard rule). A model
    process or the orchestrator may hold a message only for the in-flight turn.
    ``append`` persists one message at the end of a session's history; ``history``
    returns that session's full history in append order (empty when unknown).
    ``list_sessions`` returns at most ``limit`` recent chats, most-recently-active first,
    as ``SessionSummary`` values (ADR-0021) for the overlay's chat list/switcher/cycling;
    it is a read over the same state, adding no write path. ``set_title`` persists a
    brain-generated display title for a session (ADR-0021 titles addendum), which
    ``list_sessions`` prefers over the first-message derivation and a later call overwrites;
    it writes only a derived display value, never conversation content, and lives in the store
    like the rest so it survives a model swap. Failures surface as ``SessionStoreError``.
    """

    async def append(self, session_id: str, message: Message) -> None: ...

    async def history(self, session_id: str) -> Sequence[Message]: ...

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]: ...

    async def set_title(self, session_id: str, title: str) -> None: ...


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


class MemoryStore(Protocol):
    """Durable, cross-session memory: append one record, retrieve the top-k by similarity.

    ``add`` persists one ``MemoryRecord`` that the caller builds (id, timestamp, embedding,
    scope), so the store only translates, as ``SessionStore.append`` does. ``search`` returns
    the ``k`` records whose embeddings are most similar to ``embedding``, most-similar first;
    ``scopes`` restricts the candidate set to those namespaces (ADR-0008 scoping addendum) and
    defaults to ``None``, which ranks over ALL memories, the global-space v1 behavior. Failures
    surface as ``MemoryStoreError``.
    """

    async def add(self, record: MemoryRecord) -> None: ...

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]: ...


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


class TaskStore(Protocol):
    """Hot store for in-flight subagent tasks and their results (Redis; ADR-0010).

    A subagent is a stateless function over this store: ``put_task`` persists the delegated
    task, ``get_task`` loads it by id (the runner reads only the store, never cortex memory),
    ``put_result`` persists the outcome, and ``get_result`` returns it for the cortex to read
    (``None`` until the subagent has finished). Task state lives here, never in a model process, per
    the one hard rule, for delegation. Failures surface as ``TaskStoreError``.
    """

    async def put_task(self, task: SubagentTask) -> None: ...

    async def get_task(self, task_id: str) -> SubagentTask | None: ...

    async def put_result(self, result: SubagentResult) -> None: ...

    async def get_result(self, task_id: str) -> SubagentResult | None: ...


class ScheduleStore(Protocol):
    """Durable schedules with a fenced claim→finish protocol (ADR-0025).

    A schedule outlives every model swap and restart (the one hard rule), so items live
    only here. ``claim_due`` claims items due at ``now``, plus FIRING items whose
    ``lease`` expired (a crash or overrun mid-fire), taken oldest-due-first, at most ``limit``,
    each under a fresh fencing token: firing is at-least-once, and a record that fails to
    decode on this path is quarantined (dead-lettered, logged loudly), never a poison pill
    that halts the pass. ``finish`` persists one fire (fire-time taint ORs onto the item;
    ``next_due`` re-arms, ``None`` is terminal and the item is deleted unless deliverable) and
    ``release`` un-claims (FIRING → PENDING, due unchanged); both apply only under the
    claim's token and no-op ``False`` for a stale claimant. ``cancel`` deletes outright, and
    it sticks through an in-flight fire, returning ``False`` only for an unknown id.
    ``snooze`` postpones a one-shot to ``until``; a fired-but-undelivered reminder re-arms
    with deliverability cleared, while a recurring, FIRING, or unknown item answers
    ``False``, and the transition is fenced like the rest (ADR-0025 snooze addendum).
    ``edit`` retexts / re-recurs a non-FIRING item in place (``due_at`` untouched, so the next
    occurrence is unchanged and only future re-arms take the new cadence); the editing turn's
    taint ORs onto the item, and a FIRING or unknown item answers ``False`` (edit addendum).
    ``deliverable`` lists fired reminders awaiting ``ack`` (which clears the slot and
    deletes a DONE one-shot). ``list_active`` is PENDING/FIRING plus deliverable, due
    order. Failures surface as ``ScheduleStoreError``.
    """

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
    waiting forever; that refusal is the budget's one wall, and any implementation owes it, since
    ``SubagentRunner`` degrades exactly this error to an ``ok=False`` result instead of letting an
    exception kill the turn (ADR-0012 admission-wall addendum). The budget binds nothing it did not
    admit (no ``.wslconfig``/parent cgroup, the user's constraint), which is the sense in which it
    is *soft*; it is distinct from the ``ModelManager``'s GPU lease and the ``SubagentPlacer``'s
    VRAM ledger. The three compose at the runner (ADR-0010 decision 6, ADR-0012).
    """

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...
