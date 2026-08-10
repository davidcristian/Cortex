"""Adapter builders for the composition root: pick each port's adapter from config."""

import logging
from collections.abc import Awaitable, Callable
from functools import partial

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    AggregateToolRegistry,
    BodyGateway,
    EchoInferenceBackend,
    FilteredToolRegistry,
    GatedToolRegistry,
    InferenceBackend,
    ModelManager,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    StrictUrlRedactingGuardrail,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.config import BodyConfig, InferenceConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.dispatch_builders import build_builtin_tools, build_cortex_tools
from cortex_tools import ReconnectingMcpToolRegistry, streamable_http_session

__all__ = [
    "LLAMACPP_CONNECT_TIMEOUT_S",
    "build_body_gateway",
    "build_builtin_tools",
    "build_cortex_tools",
    "build_generation_client",
    "build_inference_backend",
    "build_output_guardrail",
    "build_tool_registry",
    "noop_aclose",
]

# Connect/write/pool time out fast on a dead server, one knob for every tier: a dead server is
# dead at the same speed everywhere. The read phase is the factory's argument, not this.
LLAMACPP_CONNECT_TIMEOUT_S = 10.0


def build_generation_client(stall_timeout_s: float) -> httpx.AsyncClient:
    """The client a llama-server generation stream rides (ADR-0005 stall-ceiling addendum)."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=stall_timeout_s)
    )


_logger = logging.getLogger(__name__)


def _report_sidecar_unavailable(name: str, error: ToolError) -> None:
    """The skip-and-report reporter: degradation is a logged warning, never silent."""
    _logger.warning(
        "tool sidecar unavailable; serving without it",
        extra={"sidecar": name, "error": str(error)},
    )


async def noop_aclose() -> None:
    """The closer for a capability that held no resources; shared by every builder module."""
    return


def build_inference_backend(
    config: InferenceConfig, cortex_model: str, *, manager: ModelManager | None = None
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it."""
    if config.backend == "llamacpp":
        client = build_generation_client(config.stall_timeout_s)
        leases = (
            manager
            if manager is not None
            else SingleResidentModelManager(cortex_model, config.endpoint)
        )
        return LlamaCppBackend(leases, client), client.aclose
    return EchoInferenceBackend(), noop_aclose


def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009)."""
    if config.backend != "mcp":
        return None, noop_aclose
    registries: list[ToolRegistry] = []
    for name, url in config.named_endpoints.items():
        registry: ToolRegistry = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
        allow = config.allow.get(name)
        if allow:
            registry = FilteredToolRegistry(registry, allow=allow)
        if config.on_unavailable == "skip":
            registry = SkipUnavailableToolRegistry(
                registry, name=name, report=_report_sidecar_unavailable
            )
        registries.append(registry)
    root = registries[0] if len(registries) == 1 else AggregateToolRegistry(registries)
    if config.gated:
        root = GatedToolRegistry(root, gated=config.gated)
    return root, noop_aclose


def build_output_guardrail(
    mode: str,
) -> UrlRedactingGuardrail | StrictUrlRedactingGuardrail | None:
    """The turn's output guardrail, or None when disabled (ADR-0015)."""
    if mode == "strict":
        return StrictUrlRedactingGuardrail()
    return UrlRedactingGuardrail() if mode == "redact" else None


async def build_body_gateway(
    config: BodyConfig, *, token: str
) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]:
    """Pick the body gateway from config; return it with the coroutine that releases it (ADR-0023).
    """
    if config.backend != "grpc":
        return None, noop_aclose
    return await GrpcBodyGateway.connect(
        config.endpoint, token=token, capture_timeout_s=config.capture_timeout_s
    )
