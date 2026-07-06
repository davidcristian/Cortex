"""Cortex orchestrator: the thin gRPC shell hosting BrainService (logic lives in cortex_core)."""

from cortex_orchestrator.auth import SEAM_TOKEN_HEADER, SeamTokenInterceptor
from cortex_orchestrator.builders import (
    build_cortex_tools,
    build_history_window,
    build_inference_backend,
    build_memory,
    build_output_guardrail,
    build_tool_registry,
    memory_scope_from_name,
)
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    SubagentRosterEntry,
    SubagentsConfig,
    ToolsConfig,
)
from cortex_orchestrator.converse import (
    DEFAULT_MAX_BUFFERED_EVENTS,
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    converse,
)
from cortex_orchestrator.server import ORCHESTRATOR_VERSION, BrainService, create_server, serve
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.wiring import run_from_env

__all__ = [
    "DEFAULT_MAX_BUFFERED_EVENTS",
    "ERROR_CODE_INFERENCE_FAILED",
    "ERROR_CODE_INTERNAL",
    "ERROR_CODE_SESSION_STORE_UNAVAILABLE",
    "ORCHESTRATOR_VERSION",
    "SEAM_TOKEN_HEADER",
    "BrainRuntimeConfig",
    "BrainService",
    "InferenceConfig",
    "MemoryConfig",
    "SeamServerConfig",
    "SeamTokenInterceptor",
    "SubagentRosterEntry",
    "SubagentsConfig",
    "ToolsConfig",
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
