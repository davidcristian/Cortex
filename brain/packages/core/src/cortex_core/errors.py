"""Typed errors of the core: adapters wrap backend failures into these (cause chained)."""

from enum import Enum


class SessionStoreError(Exception):
    """A SessionStore operation failed (store adapters wrap their backend's errors)."""


class InferenceError(Exception):
    """An InferenceBackend failed to produce or continue a completion."""


class MalformedToolCallError(InferenceError):
    """The server answered and the tool call the model wrote could not be assembled."""


class MemoryStoreError(Exception):
    """A MemoryStore operation failed (memory adapters wrap their backend's errors)."""


class MemoryDataError(MemoryStoreError):
    """The store answered and what came back is not something this repo can read."""


class EmbedderError(Exception):
    """An Embedder failed to produce an embedding (adapters wrap their backend's errors)."""


class ToolError(Exception):
    """A ToolRegistry could not dispatch a call (adapters wrap their backend's errors)."""


class ToolNotFoundError(ToolError):
    """invoke() named a tool the registry does not have."""


class TaskStoreError(Exception):
    """A TaskStore operation failed (task-store adapters wrap their backend's errors)."""


class PreferenceStoreError(Exception):
    """A PreferenceStore operation failed (preference adapters wrap their backend's errors)."""


class HandoffStoreError(Exception):
    """A HandoffStore operation failed (handoff adapters wrap their backend's errors)."""


class SubagentAdmissionError(Exception):
    """A SubagentScheduler refused a spawn rather than queuing it: no admission is coming."""


class BodyFailure(Enum):
    """How far a ``BodyGateway`` call got before it failed."""

    UNREACHABLE = "unreachable"
    """No answer arrived at all, for want of a route or of time. The only kind that may tell
    the caller the body could not be reached."""

    REFUSED = "refused"
    """The body answered and declined by policy (screen capture switched off, a rejected
    token), not for a temporary reason, so a retry changes nothing."""

    UNSUPPORTED = "unsupported"
    """The body answered and has no such capability: an RPC it does not implement, or a body
    older than the brain calling it."""

    UNREADY = "unready"
    """The body answered and the host state the call needs is not there (no display, no audio
    endpoint, no notification service). It works again once the user fixes the state."""

    OVERSIZE = "oversize"
    """The work was done and its result will not fit the size limit for one message. Not a
    fault, because nothing is broken: the same call keeps returning the same thing."""

    FAULTED = "faulted"
    """Anything else: an OS fault, an answer the brain will not accept, a bound this
    deployment cannot ask for. It is the default, so an unclassified failure says nothing
    specific rather than claiming the body was out of reach."""


class BodyGatewayError(Exception):
    """A BodyGateway call failed, with the ``BodyFailure`` kind that says how."""

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
    """A residency scope could not swap its model in, so the handoff does not run."""


class HandoffInProgressError(ModelManagerError):
    """Another handoff is already swapping, so this one never started."""


class ResidencyRestoreError(ModelManagerError):
    """The cortex could not be restored after a swap, even on the retry."""


class ModelHostError(Exception):
    """A ModelHost operation failed: a model process could not be started, stopped, or probed."""


class ModelNotHostedError(ModelHostError):
    """The host has no such logical model at all, so no wait and no retry will produce one."""
