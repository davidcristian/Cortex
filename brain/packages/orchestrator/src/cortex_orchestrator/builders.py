"""Adapter builders for the composition root: pick each port's adapter from config."""

import logging
from collections.abc import Awaitable, Callable
from functools import partial

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    AggregateToolRegistry,
    BodyGateway,
    BoundedToolRegistry,
    EchoInferenceBackend,
    FilteredToolRegistry,
    GatedToolRegistry,
    InferenceBackend,
    LookalikeUrlRedactingGuardrail,
    ModelManager,
    OutputGuardrail,
    OwnTextToolRegistry,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    StrictUrlRedactingGuardrail,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_inference import (
    TRACE_BUDGET_PROBE_TIMEOUT_S,
    LlamaCppBackend,
    reads_a_trace_budget,
)
from cortex_orchestrator.config import InferenceConfig, OutputGuardrailName
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.dispatch_builders import build_builtin_tools, build_cortex_tools
from cortex_orchestrator.own_texts import EMAIL_OWN_TEXTS
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
    "resolve_send_trace_budget",
]

# Connect, write and pool, which time out fast on a dead server whatever the tier. The read
# phase is the caller's argument instead, since the worst legitimate silence differs per tier.
LLAMACPP_CONNECT_TIMEOUT_S = 10.0


def build_generation_client(stall_timeout_s: float) -> httpx.AsyncClient:
    """The client a llama-server generation stream is read over."""
    # ``stall_timeout_s`` is httpx's read timeout, which bounds one socket read and never the
    # whole request, so a stream whose chunks keep arriving may run as long as the model takes.
    return httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=stall_timeout_s)
    )


_logger = logging.getLogger(__name__)


def _report_sidecar_unavailable(name: str, error: ToolError) -> None:
    """The skip-and-report reporter: degradation is logged as a warning rather than passed over."""
    _logger.warning(
        "tool sidecar unavailable; serving without it",
        extra={"sidecar": name, "error": str(error)},
    )


async def noop_aclose() -> None:
    """The closer for a capability that held no resources; shared by every builder module."""
    return


async def resolve_send_trace_budget(config: InferenceConfig, cortex_model: str) -> bool:
    """Whether a request to this deployment may include its own trace budget."""
    if config.send_trace_budget == "off":
        return False
    if config.send_trace_budget == "on":
        return True
    async with httpx.AsyncClient(timeout=TRACE_BUDGET_PROBE_TIMEOUT_S) as client:
        return await reads_a_trace_budget(config.endpoint, cortex_model, client)


async def build_inference_backend(
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
        send = await resolve_send_trace_budget(config, cortex_model)
        return LlamaCppBackend(leases, client, send_trace_budget=send), client.aclose
    return EchoInferenceBackend(), noop_aclose


def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None."""
    if config.backend != "mcp":
        return None, noop_aclose
    registries: list[ToolRegistry] = []
    for name, url in config.named_endpoints.items():
        dialing = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
        registry: ToolRegistry = BoundedToolRegistry(dialing, timeout_s=config.call_timeout_s)
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
    return OwnTextToolRegistry(root, own=EMAIL_OWN_TEXTS), noop_aclose


def build_output_guardrail(mode: OutputGuardrailName) -> OutputGuardrail | None:
    """The turn's output guardrail, or None when disabled."""
    if mode == "strict":
        return StrictUrlRedactingGuardrail()
    if mode == "lookalike":
        return LookalikeUrlRedactingGuardrail()
    return UrlRedactingGuardrail() if mode == "redact" else None


async def build_body_gateway(
    config: BodyConfig, *, token: str
) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]:
    """Pick the body gateway from config; return it with the coroutine that releases it."""
    if config.backend != "grpc":
        return None, noop_aclose
    return await GrpcBodyGateway.connect(
        config.endpoint,
        token=token,
        capture_timeout_s=config.capture_timeout_s,
        call_timeout_s=config.call_timeout_s,
    )
