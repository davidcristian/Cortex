"""Model host: supervisor sidecar + ModelHost adapter (docs/modules/brain-model-manager.md)."""

from cortex_model_manager.adapter import HttpModelHost
from cortex_model_manager.api import build_app, model_host_lifespan, nothing_to_close
from cortex_model_manager.boot_fit import BOOT_FREE_FLOOR_MIB, BootFit
from cortex_model_manager.children import (
    AsyncioChild,
    AsyncioChildProcesses,
    ChildProcess,
    ChildProcesses,
)
from cortex_model_manager.config import ModelHostConfig
from cortex_model_manager.device_memory import (
    DeviceMemoryProbe,
    NoDeviceMemory,
    NvidiaSmiMemory,
)
from cortex_model_manager.model_files import ModelFiles
from cortex_model_manager.probe import HealthProbe, HttpHealthProbe
from cortex_model_manager.restarts import RestartBudget, RestartPolicy
from cortex_model_manager.server import (
    boot_models,
    build_model_host,
    build_supervisor,
    main,
    tier_settings,
)
from cortex_model_manager.spec import ModelSpec, RosterError, build_roster
from cortex_model_manager.supervisor import (
    DEFAULT_PROBE_TIMEOUT_S,
    DEFAULT_REAP_TIMEOUT_S,
    DEFAULT_STOP_GRACE_S,
    ModelStatus,
    ModelSupervisor,
    SupervisorError,
    UnknownModelError,
)
from cortex_model_manager.tiers import TierArgs, llama_server_argv, tier_spec

__all__ = [
    "BOOT_FREE_FLOOR_MIB",
    "DEFAULT_PROBE_TIMEOUT_S",
    "DEFAULT_REAP_TIMEOUT_S",
    "DEFAULT_STOP_GRACE_S",
    "AsyncioChild",
    "AsyncioChildProcesses",
    "BootFit",
    "ChildProcess",
    "ChildProcesses",
    "DeviceMemoryProbe",
    "HealthProbe",
    "HttpHealthProbe",
    "HttpModelHost",
    "ModelFiles",
    "ModelHostConfig",
    "ModelSpec",
    "ModelStatus",
    "ModelSupervisor",
    "NoDeviceMemory",
    "NvidiaSmiMemory",
    "RestartBudget",
    "RestartPolicy",
    "RosterError",
    "SupervisorError",
    "TierArgs",
    "UnknownModelError",
    "boot_models",
    "build_app",
    "build_model_host",
    "build_roster",
    "build_supervisor",
    "llama_server_argv",
    "main",
    "model_host_lifespan",
    "nothing_to_close",
    "tier_settings",
    "tier_spec",
]
