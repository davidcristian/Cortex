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


class BodyGatewayError(Exception):
    """A BodyGateway call failed. The body was unreachable or the OS action errored.

    The gRPC adapter wraps its transport failures (a refused dial, a non-OK status) into this,
    cause chained; the volume tools catch it and return an ``is_error`` result so the cortex
    hears about a dead body and can recover, never a turn-killing crash.
    """


class ModelManagerError(Exception):
    """A ModelManager operation failed; adapters wrap their backend's errors into this."""


class ModelUnavailableError(ModelManagerError):
    """acquire() was asked for a model that is not the resident one (no swap in v1)."""
