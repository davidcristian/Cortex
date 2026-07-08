"""Cortex orchestrator: the thin gRPC shell hosting BrainService (logic lives in cortex_core)."""

from cortex_orchestrator.auth import SeamTokenInterceptor
from cortex_orchestrator.builders import (
    build_body_gateway,
    build_cortex_tools,
    build_history_window,
    build_inference_backend,
    build_memory,
    build_output_guardrail,
    build_tool_registry,
    memory_scope_from_name,
)
from cortex_orchestrator.config import (
    BodyConfig,
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    ToolsConfig,
)
from cortex_orchestrator.config_subagents import SubagentRosterEntry, SubagentsConfig
from cortex_orchestrator.confirm import SeamConfirmer
from cortex_orchestrator.converse import (
    DEFAULT_CONFIRM_TIMEOUT_S,
    DEFAULT_MAX_BUFFERED_EVENTS,
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    EngineFactory,
    converse,
)
from cortex_orchestrator.server import (
    DEFAULT_SESSION_LIST_LIMIT,
    MAX_SESSION_LIST_LIMIT,
    ORCHESTRATOR_VERSION,
    BrainService,
    create_server,
    serve,
)
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.wiring import run_from_env
from cortex_seam import SEAM_TOKEN_HEADER

__all__ = [
    "DEFAULT_CONFIRM_TIMEOUT_S",
    "DEFAULT_MAX_BUFFERED_EVENTS",
    "DEFAULT_SESSION_LIST_LIMIT",
    "ERROR_CODE_INFERENCE_FAILED",
    "ERROR_CODE_INTERNAL",
    "ERROR_CODE_SESSION_STORE_UNAVAILABLE",
    "MAX_SESSION_LIST_LIMIT",
    "ORCHESTRATOR_VERSION",
    "SEAM_TOKEN_HEADER",
    "BodyConfig",
    "BrainRuntimeConfig",
    "BrainService",
    "EngineFactory",
    "InferenceConfig",
    "MemoryConfig",
    "SeamConfirmer",
    "SeamServerConfig",
    "SeamTokenInterceptor",
    "SubagentRosterEntry",
    "SubagentsConfig",
    "ToolsConfig",
    "build_body_gateway",
    "build_cortex_tools",
    "build_history_window",
    "build_inference_backend",
    "build_memory",
    "build_output_guardrail",
    "build_subagent_tools",
    "build_subagents",
    "build_tool_registry",
    "converse",
    "create_server",
    "memory_scope_from_name",
    "run_from_env",
    "serve",
]
