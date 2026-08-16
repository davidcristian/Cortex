"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
The six state-store ports (session, memory, task, schedule, handoff, preference) live in
``ports_stores.py``, the three model-lifecycle ports (``ModelHost``, ``ResidencyController``,
``ResidencyReporter``) in ``ports_models.py``, ``SubagentPlacer`` in ``ports_placement.py``, and
``BodyGateway`` in ``ports_body.py``; all four sets are re-exported here, so
``from cortex_core.ports import SessionStore`` keeps resolving.
"""

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
from cortex_core.ports_models import ModelHost, ResidencyController, ResidencyReporter
from cortex_core.ports_placement import SubagentPlacer
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

# The six state-store ports live in ``ports_stores.py``, the three model-lifecycle ports in
# ``ports_models.py``, ``SubagentPlacer`` in ``ports_placement.py`` and ``BodyGateway`` in
# ``ports_body.py`` (line-cap splits); the explicit export list re-exports them alongside the
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
    """One stateless streamed completion against a loaded model, with no sessions and no retries.

    ``stream`` yields the reply to ``messages`` as ``InferenceEvent``s: ``TextChunk`` deltas
    of assistant text, interleaved with ``ToolCall``s when the model asks to run a tool from
    ``tools`` (native function-calling, ADR-0009). With ``tools`` empty the stream is text
    only, exactly as before. ``model`` is a logical id (ADR-0004), never a file path.
    ``schema`` (ADR-0028), when set, constrains decoding so every emitted token conforms to
    that JSON Schema; ``None`` (the default, every caller but a constrained tool-less subagent)
    leaves output unconstrained. **Images ride the messages**, not this signature (ADR-0029): a
    ``Message`` may carry ``images``, and an adapter that supports them serialises the pair
    together. A per-request keyword could not express "the image from round one" in round three
    without the caller re-threading it, which is why the port did not have to change at all.
    ``bounds`` (ADR-0038 cheap-fold addendum) is how far this one request lets the model go, per
    REQUEST because one resident cortex both answers the user, where deliberation earns its wait,
    and folds a recap, where it is discarded unread. Failures surface as ``InferenceError``.
    **A backend whose engine says why a completion ended closes it with one ``DecodeStop``**
    (ADR-0005 finish-reason addendum) and **a backend whose engine reports how fast it decoded
    closes the stream with one ``DecodeCadence``** (ADR-0030 spill-watch addendum), in that order
    and both after the text they describe, since neither is knowable until the tokens are counted.
    Reporting either is optional and the two are independent, an engine that offers no timings
    still being able to say what stopped it. Silence is a legitimate implementation of both and
    says only that the engine offered nothing, so no consumer may read a missing cadence as a
    healthy rate or a missing stop as a model that finished.
    """

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
    """Owns the single GPU: leases the resident model, serializes callers (ADR-0007).

    ``acquire(model)`` returns an async context manager that queues for GPU access and
    yields a ``ModelLease`` for the block's duration; leaving the block releases the GPU
    to the next waiter. v1 holds one resident model and performs no swap, so acquiring any
    other id raises ``ModelUnavailableError``. Failures surface as ``ModelManagerError``.
    Subagent VRAM placement is a separate concern behind ``SubagentPlacer`` (ADR-0012), so
    this port (and Slice 11's swap that reuses ``acquire``) stays unchanged.
    """

    def acquire(self, model: str) -> AbstractAsyncContextManager[ModelLease]: ...


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


class TurnRunner(Protocol):
    """Runs one user turn as a stream of domain events: what a ``Converse`` stream drives.

    The seam between the orchestrator's stream plumbing and whichever engine serves a turn.
    ``TurnEngine`` is the plain implementation; ``EscalatingTurnEngine`` wraps it to carry a
    brain handoff inside the same turn (ADR-0030 decision 5/6), which is why the servicer's
    engine factory is typed to this protocol rather than to the concrete engine. The event
    contract is the engine's: zero or more ``TextDelta``/``StatusUpdate``/``ToolActivity``,
    then exactly one ``TurnCompleted``, and closing the returned generator tears the turn down
    (the user message stays persisted, a partial reply is dropped).
    """

    def handle_turn(self, session_id: str, text: str) -> AsyncGenerator[TurnEvent, None]: ...


class ToolRegistry(Protocol):
    """The tools the cortex can call, and the one gateway that runs a call (ADR-0009).

    ``describe_tools`` lists what is available (name + JSON-Schema parameters) to advertise
    to the model; ``invoke`` runs one call and returns a ``ToolResult`` whose ``is_error``
    reflects whether the *tool* failed. A dispatch failure (unknown tool, transport) surfaces
    as ``ToolError`` (``ToolNotFoundError`` for an unknown name); the dispatcher, not the
    registry, turns that into an error result the model can read.

    **A listing is read at the call, never remembered.** ``AggregateToolRegistry`` and
    ``UngatedToolRegistry`` resolve ownership and gating by walking ``describe_tools`` on every
    invoke, so an implementation answering from a set it cached at construction would route to a
    tool its server has since dropped, and would advertise a gated one as ungated.

    **What an unknown name looks like depends on who is asked, and only the safety half is
    common.** The core's own registries know their whole set and raise ``ToolNotFoundError``. A
    remote one can only report what its server says, and an MCP server answers an unknown tool
    with an error *result*, so ``McpToolRegistry`` returns ``is_error`` there rather than raising.
    What every implementation owes is that a name it does not serve never comes back as a
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


class RecallAuditSink(Protocol):
    """The trail that answers "why did recall return these?" (ADR-0038 decision 5).

    ``record`` takes one ``RecallAudit`` per recall, awaited after the policy has selected, so a
    recall is audited whichever policy ran and whether or not it returned anything. The audit
    carries the ranking, meaning each kept hit's key and the basis naming what that key is, which
    is the first code in the tree to read a policy's own rank key. It carries the candidates the
    rank **dropped** too, by id and the store's cosine, bounded and counting what the bound left
    out, and with no key beside them, a rank having no opinion to record about what it passed over
    (ADR-0038 dropped-candidate addendum).

    The value carries conversation content (the query, the recalled text), so a sink decides what
    it keeps of them; the shipped ``LoggingRecallSink`` keeps neither, exactly as the tool audit's
    own adapter logs a result's size rather than its bytes. The fake keeps them in memory for
    assertions.
    """

    async def record(self, audit: RecallAudit) -> None: ...


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


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget. Concurrency, not the GPU (ADR-0012).

    ``admit(request)`` returns an async context manager that yields once the request's ``cpus``/
    ``memory_gb`` fit the remaining budget (summed admitted ``cpus`` ≤ cpu target AND summed
    ``memory_gb`` ≤ memory target) and releases both on exit; over budget, callers wait (depth-1
    delegation guarantees no spawn waits on another spawn, so this cannot deadlock). A charge larger
    than the whole budget can never be admitted, so it raises ``SubagentAdmissionError`` rather than
    waiting forever; any implementation owes that refusal, since ``SubagentRunner`` degrades exactly
    this error to an ``ok=False`` result instead of letting an exception kill the turn (ADR-0012
    admission-wall addendum). **An implementation that queues owes a bound on that queue** and the
    same typed refusal when it elapses (the bounded-admission-wait addendum): a wait nothing ends
    is a turn that never finishes, and the caller cannot supply the bound, since ``admit``'s
    signature has nowhere to carry one and the wait is policy the budget owns rather than a
    per-spawn ask. How long is the implementation's own configuration; a twin that admits
    everything at once, having no queue, satisfies this vacuously. The budget binds nothing it did
    not admit (no ``.wslconfig``/parent cgroup, the user's constraint), which is the sense in which
    it is *soft*; it is distinct from
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
