"""Ports of the pure core (typing.Protocol): adapters implement, the core orchestrates.

Method bodies are one-line ``...`` stubs. Protocols carry contracts, never behavior.
Failures cross these boundaries exclusively as the typed errors in ``errors.py``.
The six state-store ports (session, memory, task, schedule, handoff, preference) live in
``ports_stores.py``, the four model-lifecycle ports (``ModelHost``, ``ResidencyController``,
``ResidencyReporter``, ``PaceSink``) in ``ports_models.py``, the three a tool call passes through
(``ToolRegistry``, ``Confirmer``, ``ToolAuditSink``) in ``ports_tools.py``, ``SubagentPlacer`` in
``ports_placement.py``, and ``BodyGateway`` in ``ports_body.py``; all five sets are re-exported
here, so ``from cortex_core.ports import SessionStore`` keeps resolving.
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

# The list is written out rather than left implicit because it re-exports the ports the line cap
# moved into sibling modules alongside the ones defined here, which is what keeps every existing
# ``from cortex_core.ports import ...`` and the ``cortex_core`` barrel resolving unchanged.
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
    """One stateless streamed completion against a loaded model, with no sessions and no retries.

    ``stream`` yields the reply to ``messages`` as ``InferenceEvent``s: ``TextChunk`` deltas
    of assistant text, a reasoning model's ``ReasoningChunk`` deltas before them (ADR-0020), and
    each whole ``ToolCall`` the model makes from ``tools`` (native function-calling, ADR-0009),
    which never precedes the text beside it. With ``tools`` empty the stream is text only, exactly
    as before.

    ``model`` is a logical id (ADR-0004), never a file path, and an implementation answers only
    for the ids it serves: asked for one it does not, it raises ``InferenceError`` rather than
    answering out of whatever model is behind it, since the id is the caller's whole statement of
    which weights it asks for, and a reply under the wrong one cannot be read as such. Which ids
    those are is the implementation's own business, a ``ModelManager``'s residency here and a
    router's table elsewhere, and so is where that error comes from.

    ``schema`` (ADR-0028), when set, constrains decoding so every emitted token conforms to that
    JSON Schema; ``None`` (the default, every caller but a constrained tool-less subagent) leaves
    output unconstrained. Images travel on the messages rather than in this signature (ADR-0029):
    a ``Message`` may carry ``images``, and an adapter that supports them serialises the pair
    together. A per-request keyword could not express "the image from round one" in round three
    without the caller re-threading it, which is why the port did not have to change at all.

    ``bounds`` (ADR-0038 cheap-fold addendum) is how far this one request lets the model go, and
    it is per request because one resident cortex both answers the user, where deliberation earns
    its wait, and folds a recap, where it is discarded unread. A ``bounds`` asking for no thinking
    is passed on and never enforced (ADR-0005 switch-is-advisory addendum): an implementation asks
    its deployment and reports what came back, so a trace that arrived despite the switch still
    crosses as ``ReasoningChunk`` rather than being suppressed to match what the caller asked for.
    That stream is the caller's only evidence that the switch did not hold, and a deployment where
    it does not hold is one whose cap paired with the switch deletes the reply, so an
    implementation that dropped the trace would leave that failure with nothing to read.

    Failures surface as ``InferenceError``, at a moment the port leaves open: an implementation
    may fail before it hands back an iterator or on the first event of one, and both shapes are
    live in this tree.

    A backend whose engine reports why a completion ended closes it with one ``DecodeStop``
    (ADR-0005 finish-reason addendum), and a backend whose engine reports how fast it decoded
    follows that with one ``DecodeCadence`` (ADR-0030 spill-watch addendum), in that order and
    both after the text and thinking they describe, since neither is knowable until the tokens are
    counted; any tool calls trail them, an engine that streams them in pieces having nothing whole
    to hand over until the completion is done. Reporting either is optional and the two are
    independent, an engine that offers no timings still being able to report what stopped it.
    Emitting neither is a legitimate implementation and says only that the engine offered nothing,
    so no consumer may read a missing cadence as a healthy rate or a missing stop as a model that
    finished. A completion that emits no events at all is legal for the same reason.
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
    this port (and the model swap that reuses ``acquire``) stays unchanged.
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

    A runner is told which turn it is serving (ADR-0038 named-turn addendum). ``turn_id``
    identifies this turn everywhere it is written down: it groups the user message with the
    reply in the store, names the handoff a turn that escalates records, and is what
    ``TurnCompleted`` carries back to the client. A runner that minted it instead would be the
    only holder of it, and the one path where that matters is the one where no completion event
    is ever emitted: a turn that fails is reported by its caller, which would have nothing to
    name. So identity belongs to whoever schedules the turn, and a runner is a stateless
    function of the session, the text, and the id it was handed.
    """

    def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]: ...


class RecallAuditSink(Protocol):
    """The trail that answers "why did recall return these?" (ADR-0038 decision 5).

    ``record`` takes one ``RecallAudit`` per recall, awaited after the policy has selected, so a
    recall is audited whichever policy ran and whether or not it returned anything. The audit
    carries the ranking, meaning each kept hit's key and the basis naming what that key is, which
    is the first code in the tree to read a policy's own rank key. It carries the candidates the
    rank dropped too, by id and the store's cosine, bounded and counting what the bound left out,
    and with no key beside them, a rank recording no key for what it passed over (ADR-0038
    dropped-candidate addendum).

    The value carries conversation content (the query, the recalled text), so what a sink keeps of
    them is left to the adapter; the shipped ``LoggingRecallSink`` keeps neither, exactly as the
    tool audit's own adapter logs a result's size rather than its bytes. The fake keeps them in
    memory for assertions.
    """

    async def record(self, audit: RecallAudit) -> None: ...


class SubagentScheduler(Protocol):
    """Admits subagent spawns against a soft CPU/RAM budget. Concurrency, not the GPU (ADR-0012).

    ``admit(request)`` returns an async context manager that yields once the request's ``cpus``/
    ``memory_gb`` fit the remaining budget (summed admitted ``cpus`` ≤ cpu target AND summed
    ``memory_gb`` ≤ memory target) and releases both on exit; over budget, callers wait (depth-1
    delegation guarantees no spawn waits on another spawn, so this cannot deadlock). A charge larger
    than the whole budget can never be admitted, so it raises ``SubagentAdmissionError`` rather than
    waiting forever, and every implementation must raise it, since ``SubagentRunner`` degrades
    exactly this error to an ``ok=False`` result instead of letting an exception kill the turn
    (ADR-0012 admission-wall addendum). An implementation that queues must bound that queue and
    raise the same typed error when the bound elapses (the bounded-admission-wait addendum): a wait
    nothing ends is a turn that never finishes, and the caller cannot supply the bound, since
    ``admit``'s signature has nowhere to carry one and the wait is policy the budget owns rather
    than a per-spawn ask. How long is the implementation's own configuration; a twin that admits
    everything at once, having no queue, satisfies this with nothing to do. The budget binds
    nothing it did not admit (no ``.wslconfig``/parent cgroup, the user's constraint), which is what
    makes it soft; it is distinct from the ``ModelManager``'s GPU lease and the
    ``SubagentPlacer``'s VRAM ledger. The three compose at the runner (ADR-0010 decision 6,
    ADR-0012).

    ``drain(timeout_s=...)`` quiesces the pool for a model handoff (ADR-0030 decision 4, the
    additive method ADR-0012 deferred): it stops admission at once and waits, bounded by
    ``timeout_s`` seconds, for in-flight admissions to release. From the call until ``undrain``,
    every ``admit`` raises the same typed ``SubagentAdmissionError`` instead of queuing
    (a brain-phase spawn queued against its own drain would deadlock the turn against its own
    swap), and a caller already waiting on a full budget is woken so it raises rather than
    sleeping through the swap. True means the pool drained clean; False means the bound elapsed
    with work still in flight, and nothing was killed (v1 never kills a subagent mid-stream),
    so the swap conductor must abort the handoff before evicting anything. ``undrain()``
    reverses the window, resuming normal admission; the conductor owes it in a ``finally``
    (swap-back and aborted handoff alike), so admission always resumes. Both are idempotent.
    """

    def admit(self, request: PlacementRequest) -> AbstractAsyncContextManager[None]: ...

    async def drain(self, *, timeout_s: float) -> bool: ...

    def undrain(self) -> None: ...
