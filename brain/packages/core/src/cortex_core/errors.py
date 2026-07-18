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
    """A ToolRegistry could not dispatch a call (adapters wrap their backend's errors)."""


class ToolNotFoundError(ToolError):
    """invoke() named a tool the registry does not know."""


class TaskStoreError(Exception):
    """A TaskStore operation failed (task-store adapters wrap their backend's errors)."""


class HandoffStoreError(Exception):
    """A HandoffStore operation failed (handoff adapters wrap their backend's errors)."""


class SubagentAdmissionError(Exception):
    """A SubagentScheduler refused a spawn outright: no wait could ever admit this charge."""


class BodyGatewayError(Exception):
    """A BodyGateway call failed. The body was unreachable or the OS action errored."""


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
