"""Cortex brain pure core: typed logic and ports, no I/O."""

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.engine import DEFAULT_CORTEX_MODEL, TurnEngine
from cortex_core.errors import (
    EmbedderError,
    InferenceError,
    MemoryStoreError,
    ModelManagerError,
    ModelUnavailableError,
    SessionStoreError,
    ToolError,
    ToolNotFoundError,
)
from cortex_core.events import TextDelta, TurnCompleted, TurnEvent
from cortex_core.fakes import (
    EchoInferenceBackend,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    RecordingAuditSink,
    SystemClock,
)
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.model import ModelLease, SingleResidentModelManager
from cortex_core.ports import (
    Clock,
    Embedder,
    InferenceBackend,
    MemoryStore,
    ModelManager,
    SessionStore,
    ToolAuditSink,
    ToolRegistry,
)
from cortex_core.recall import MemoryRecaller
from cortex_core.routing import RoutingHints, Tier, route_turn
from cortex_core.tools import ToolCall, ToolInvocation, ToolResult, ToolSpec

__all__ = [
    "DEFAULT_CORTEX_MODEL",
    "Clock",
    "EchoInferenceBackend",
    "Embedder",
    "EmbedderError",
    "HashEmbedder",
    "InMemoryMemoryStore",
    "InMemorySessionStore",
    "InMemoryToolRegistry",
    "InferenceBackend",
    "InferenceError",
    "MemoryRecaller",
    "MemoryRecord",
    "MemoryStore",
    "MemoryStoreError",
    "Message",
    "ModelLease",
    "ModelManager",
    "ModelManagerError",
    "ModelUnavailableError",
    "RecordingAuditSink",
    "Role",
    "RoutingHints",
    "ScoredMemory",
    "SessionStore",
    "SessionStoreError",
    "SingleResidentModelManager",
    "SystemClock",
    "TextDelta",
    "Tier",
    "ToolAuditSink",
    "ToolCall",
    "ToolDispatcher",
    "ToolError",
    "ToolInvocation",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "TurnCompleted",
    "TurnEngine",
    "TurnEvent",
    "route_turn",
]
