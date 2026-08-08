"""Public core names for in-memory test doubles for the ports above, shared across the workspace.

One of the area sub-barrels the ``cortex_core`` barrel re-exports wholesale, so the
import path for every name below stays ``cortex_core``. ``__all__`` is what that
wildcard re-exports, and it is this file's contract.
"""

from cortex_core.fakes import (
    EchoInferenceBackend,
    HashEmbedder,
    InMemoryMemoryStore,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    RecordingProgressSink,
    RecordingRecallSink,
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
