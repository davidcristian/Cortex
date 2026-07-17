"""Typed errors of the core: adapters wrap backend failures into these (cause chained).

Core code raises and propagates only typed errors. There is never a bare Exception, and no
adapter-specific exception ever crosses a port boundary.
"""


class SessionStoreError(Exception):
    """A SessionStore operation failed (store adapters wrap their backend's errors)."""


class InferenceError(Exception):
    """An InferenceBackend failed to produce or continue a completion."""


class MemoryStoreError(Exception):
    """A MemoryStore operation failed (memory adapters wrap their backend's errors)."""


class EmbedderError(Exception):
    """An Embedder failed to produce an embedding (adapters wrap their backend's errors)."""


class ToolError(Exception):
    """A ToolRegistry could not dispatch a call (adapters wrap their backend's errors).

    The dispatcher turns this into an ``is_error`` ``ToolResult`` so the model hears about
    the failure and can recover; a tool that ran but reported its own error is a normal
    ``is_error`` result, not this exception.
    """


class ToolNotFoundError(ToolError):
    """invoke() named a tool the registry does not know."""


class TaskStoreError(Exception):
    """A TaskStore operation failed (task-store adapters wrap their backend's errors)."""


class HandoffStoreError(Exception):
    """A HandoffStore operation failed (handoff adapters wrap their backend's errors)."""


class SubagentAdmissionError(Exception):
    """A SubagentScheduler refused a spawn outright: no wait could ever admit this charge.

    The budget's one hard refusal (ADR-0012 admission-wall addendum), distinct from queuing:
    a charge within the budget always eventually fits as peers release, so it waits, while a
    charge larger than the whole budget never does. Typed rather than a bare ``ValueError``
    because ``SubagentRunner`` catches exactly this and degrades it to an ``ok=False``
    ``SubagentResult``; catching ``ValueError`` there would swallow unrelated value errors.
    Construction-time validation (a non-positive budget, a non-positive ask) stays ``ValueError``
    like every other frozen value type's, since that is a bad *value*, not a refused request.
    """


class BodyGatewayError(Exception):
    """A BodyGateway call failed. The body was unreachable or the OS action errored.

    The gRPC adapter wraps its transport failures (a refused dial, a non-OK status) into this,
    cause chained; the volume tools catch it and return an ``is_error`` result so the cortex
    hears about a dead body and can recover, never a turn-killing crash.
    """


class ScheduleStoreError(Exception):
    """A ScheduleStore operation failed (schedule adapters wrap their backend's errors).

    A store-down signal, not a poison record: per-record corruption on the claim path is
    quarantined inside the adapter (ADR-0025 decision 1), so the ticker treats this error
    as transient (log, skip the pass, retry next poll).
    """


class ModelManagerError(Exception):
    """A ModelManager operation failed; adapters wrap their backend's errors into this."""


class ModelUnavailableError(ModelManagerError):
    """acquire() was asked for a model that is not resident, and no scope will make it so."""


class SwapFailedError(ModelManagerError):
    """A residency scope could not swap its model in, so the handoff is off (ADR-0030).

    Raised on scope ENTRY: the model failed to start, its readiness gate reported ``FAILED``, or
    the gate's bound elapsed. The scope's own ``finally`` has already restored the cortex by the
    time this surfaces, so a caller catching it is back on a serving cortex and owes the user an
    honest note, never a retry loop.
    """


class ResidencyRestoreError(ModelManagerError):
    """The cortex could not be restored after a swap, even on the retry (ADR-0030 decision 4).

    The one failure the design cannot recover from in code: the GPU holds nothing servable, so
    the scope logs loudly and raises this from its exit. The runbook owns manual recovery, and
    the compose ``restart`` policy plus boot recovery converge a revived host on the next start.
    """


class ModelHostError(Exception):
    """A ModelHost operation failed: a model process could not be started, stopped, or probed.

    The typed boundary of the process-lifecycle port (ADR-0030 decision 3). The swap turns it
    into a ``SwapFailedError`` or an aborted restore rather than letting an adapter's transport
    failure reach a turn.
    """
