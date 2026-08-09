"""Typed errors of the core: adapters wrap backend failures into these (cause chained).

Core code raises and propagates only typed errors. There is never a bare Exception, and no
adapter-specific exception ever crosses a port boundary.
"""

from enum import Enum


class SessionStoreError(Exception):
    """A SessionStore operation failed (store adapters wrap their backend's errors)."""


class InferenceError(Exception):
    """An InferenceBackend failed to produce or continue a completion."""


class MemoryStoreError(Exception):
    """A MemoryStore operation failed (memory adapters wrap their backend's errors)."""


class EmbedderError(Exception):
    """An Embedder failed to produce an embedding (adapters wrap their backend's errors)."""


class ToolError(Exception):
    """A ToolRegistry could not dispatch a call (adapters wrap their backend's errors)."""


class ToolNotFoundError(ToolError):
    """invoke() named a tool the registry does not know."""


class TaskStoreError(Exception):
    """A TaskStore operation failed (task-store adapters wrap their backend's errors)."""


class PreferenceStoreError(Exception):
    """A PreferenceStore operation failed (preference adapters wrap their backend's errors)."""


class HandoffStoreError(Exception):
    """A HandoffStore operation failed (handoff adapters wrap their backend's errors)."""


class SubagentAdmissionError(Exception):
    """A SubagentScheduler refused a spawn rather than queuing it: no admission is coming."""


class BodyFailure(Enum):
    """How far a ``BodyGateway`` call got before it failed (ADR-0023 2026-08-08 addendum)."""

    UNREACHABLE = "unreachable"
    """No answer arrived at all, whether for want of a route or of time. The only kind that may
    tell the caller the body could not be reached."""

    REFUSED = "refused"
    """The body answered and declined: a standing policy answer (screen capture switched off, a
    rejected seam token), not a transient one, so retrying it changes nothing."""

    UNSUPPORTED = "unsupported"
    """The body answered and has no such capability: an RPC it does not implement, or a body
    older than the brain calling it."""

    UNREADY = "unready"
    """The body answered and the host state the call needs is not there (no display, no audio
    endpoint, no notification service). It works again once the user fixes the state."""

    OVERSIZE = "oversize"
    """The work was done and its result will not fit the seam's budget. Distinct from a fault
    because nothing is broken: the same call will keep answering the same way."""

    FAULTED = "faulted"
    """Anything else: an OS fault, an answer the brain will not vouch for, a bound this
    deployment cannot ask for. The default, deliberately, so a failure nobody classified says
    the honest uninformative thing rather than claiming the body was out of reach."""


class BodyGatewayError(Exception):
    """A BodyGateway call failed, carrying the ``BodyFailure`` kind that says how."""

    def __init__(self, message: str, *, kind: BodyFailure = BodyFailure.FAULTED) -> None:
        super().__init__(message)
        self.kind = kind


class ScheduleStoreError(Exception):
    """A ScheduleStore operation failed (schedule adapters wrap their backend's errors)."""


class ModelManagerError(Exception):
    """A ModelManager operation failed; adapters wrap their backend's errors into this."""


class ModelUnavailableError(ModelManagerError):
    """acquire() was asked for a model that is not resident, and no scope will make it so."""


class SwapFailedError(ModelManagerError):
    """A residency scope could not swap its model in, so the handoff is off (ADR-0030)."""


class HandoffInProgressError(ModelManagerError):
    """Another handoff already owns the swap, so this one never started (ADR-0030)."""


class ResidencyRestoreError(ModelManagerError):
    """The cortex could not be restored after a swap, even on the retry (ADR-0030 decision 4)."""


class ModelHostError(Exception):
    """A ModelHost operation failed: a model process could not be started, stopped, or probed."""
