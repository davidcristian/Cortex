"""Public core names for in-memory test doubles for the ports above, shared across the workspace."""

from cortex_core.fakes import (
    EchoInferenceBackend,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    RecordingProgressSink,
    SystemClock,
)
from cortex_core.fakes_body import (
    CaptureAsk,
    InMemoryBodyGateway,
    SentNotification,
    default_capture,
)
from cortex_core.fakes_handoff import InMemoryHandoffStore
from cortex_core.fakes_inference import ScriptedInferenceBackend
from cortex_core.fakes_memory import HashEmbedder, InMemoryMemoryStore, RecordingRecallSink
from cortex_core.fakes_model_host import ScriptedModelHost
from cortex_core.fakes_preferences import InMemoryPreferenceStore
from cortex_core.fakes_schedule import InMemoryScheduleStore
from cortex_core.fakes_scheduler import AdmitAllScheduler
from cortex_core.fakes_session import InMemorySessionStore
from cortex_core.fakes_sleeper import AsyncioSleeper, RecordingSleeper
from cortex_core.fakes_vision import ScriptedVisionProbe

__all__ = [
    "AdmitAllScheduler",
    "AsyncioSleeper",
    "CaptureAsk",
    "EchoInferenceBackend",
    "HashEmbedder",
    "InMemoryBodyGateway",
    "InMemoryHandoffStore",
    "InMemoryMemoryStore",
    "InMemoryPreferenceStore",
    "InMemoryScheduleStore",
    "InMemorySessionStore",
    "InMemoryTaskStore",
    "InMemoryToolRegistry",
    "RecordingAuditSink",
    "RecordingConfirmer",
    "RecordingProgressSink",
    "RecordingRecallSink",
    "RecordingSleeper",
    "ScriptedInferenceBackend",
    "ScriptedModelHost",
    "ScriptedVisionProbe",
    "SentNotification",
    "SystemClock",
    "default_capture",
]
