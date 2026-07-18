"""Model host: supervisor sidecar + ModelHost adapter (docs/modules/brain-model-manager.md)."""

from cortex_model_manager.adapter import HttpModelHost
from cortex_model_manager.api import build_app, model_host_lifespan, nothing_to_close
from cortex_model_manager.children import (
    AsyncioChild,
    AsyncioChildProcesses,
    ChildProcess,
    ChildProcesses,
)
from cortex_model_manager.config import ModelHostConfig
from cortex_model_manager.probe import HealthProbe, HttpHealthProbe
from cortex_model_manager.server import build_model_host, build_supervisor, main
from cortex_model_manager.spec import ModelSpec, RosterError, build_roster
from cortex_model_manager.supervisor import (
    DEFAULT_REAP_TIMEOUT_S,
    DEFAULT_STOP_GRACE_S,
    ModelStatus,
    ModelSupervisor,
    StopBounds,
    SupervisorError,
    UnknownModelError,
)
from cortex_model_manager.tiers import TierArgs, llama_server_argv, tier_spec

__all__ = [
    "DEFAULT_REAP_TIMEOUT_S",
    "DEFAULT_STOP_GRACE_S",
    "AsyncioChild",
    "AsyncioChildProcesses",
    "ChildProcess",
    "ChildProcesses",
    "HealthProbe",
    "HttpHealthProbe",
    "HttpModelHost",
    "ModelHostConfig",
    "ModelSpec",
    "ModelStatus",
    "ModelSupervisor",
    "RosterError",
    "StopBounds",
    "SupervisorError",
    "TierArgs",
    "UnknownModelError",
    "build_app",
    "build_model_host",
    "build_roster",
    "build_supervisor",
    "llama_server_argv",
    "main",
    "model_host_lifespan",
    "nothing_to_close",
    "tier_spec",
]
