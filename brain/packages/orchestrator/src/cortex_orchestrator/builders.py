"""Adapter builders for the composition root: pick each port's adapter from config."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from functools import partial

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    DEFAULT_DISPATCH_POLICY,
    AggregateToolRegistry,
    BodyGateway,
    BuiltinTool,
    CharBudgetHistoryWindow,
    Clock,
    CompositeToolRegistry,
    Confirmer,
    DispatchPolicy,
    EchoInferenceBackend,
    FilteredToolRegistry,
    GatedToolRegistry,
    GetVolumeTool,
    InferenceBackend,
    SetVolumeTool,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    SpawnSubagentsTool,
    StrictUrlRedactingGuardrail,
    ToolDispatcher,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.config import BodyConfig, InferenceConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_tools import (
    LoggingAuditSink,
    ReconnectingMcpToolRegistry,
    streamable_http_session,
)

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
# Public: `subagent_builders` dials its llama-servers with the same policy (one knob).
LLAMACPP_CONNECT_TIMEOUT_S = 10.0

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
    config: InferenceConfig, cortex_model: str
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it.

    Returns the no-op closer for Echo (no resources) and the HTTP client's ``aclose`` for
    llama.cpp, so the caller's shutdown path is uniform regardless of which backend ran.
    """
    if config.backend == "llamacpp":
        client = httpx.AsyncClient(timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None))
        manager = SingleResidentModelManager(cortex_model, config.endpoint)
        return LlamaCppBackend(manager, client), client.aclose
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


def build_history_window(char_budget: int) -> CharBudgetHistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014)."""
    return CharBudgetHistoryWindow(char_budget) if char_budget > 0 else None


async def build_body_gateway(
    config: BodyConfig, *, token: str
) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]:
    """Pick the body gateway from config; return it with the coroutine that releases it (ADR-0023).
    """
    if config.backend != "grpc":
        return None, noop_aclose
    return await GrpcBodyGateway.connect(config.endpoint, token=token)


def build_builtin_tools(
    spawn_tool: SpawnSubagentsTool | None,
    body: BodyGateway | None,
    schedule_tools: Sequence[BuiltinTool] = (),
) -> list[BuiltinTool]:
    """The cortex's built-in set, assembled once by the wiring (ADR-0025 decision 7)."""
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if body is not None:
        builtins.append(GetVolumeTool(body))
        builtins.append(SetVolumeTool(body))
    builtins.extend(schedule_tools)
    return builtins


def build_cortex_tools(
    tool_registry: ToolRegistry | None,
    builtins: Sequence[BuiltinTool],
    clock: Clock,
    *,
    confirmer: Confirmer | None = None,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> ToolDispatcher | None:
    """The cortex's audited dispatcher: the built-in set merged with the MCP tools."""
    if not builtins and tool_registry is None:
        return None
    registry = CompositeToolRegistry(builtins, remote=tool_registry)
    return ToolDispatcher(
        registry,
        LoggingAuditSink(),
        clock,
        confirmer=confirmer,
        policy=policy,
    )
