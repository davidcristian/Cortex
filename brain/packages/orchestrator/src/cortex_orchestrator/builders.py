"""Adapter builders for the composition root: pick each port's adapter from config."""

import logging
from collections.abc import Awaitable, Callable, Collection
from contextlib import AsyncExitStack

import httpx

from cortex_body_client import GrpcBodyGateway
from cortex_core import (
    AggregateToolRegistry,
    BodyGateway,
    BuiltinTool,
    CharBudgetHistoryWindow,
    Clock,
    CompositeToolRegistry,
    Confirmer,
    EchoInferenceBackend,
    FilteredToolRegistry,
    GatedToolRegistry,
    GetVolumeTool,
    GlobalMemoryScope,
    InferenceBackend,
    MemoryRecaller,
    MemoryScope,
    SessionMemoryScope,
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
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.config import (
    BodyConfig,
    InferenceConfig,
    MemoryConfig,
    MemoryScopeName,
    ToolsConfig,
)
from cortex_tools import LoggingAuditSink, McpToolRegistry

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
# Public: `subagent_builders` dials its llama-servers with the same policy (one knob).
LLAMACPP_CONNECT_TIMEOUT_S = 10.0
# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0

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


def memory_scope_from_name(name: MemoryScopeName) -> MemoryScope:
    """Map ``CORTEX_MEMORY_SCOPE`` to its recall-namespace policy (ADR-0008 scoping addendum)."""
    if name == "session":
        return SessionMemoryScope()
    return GlobalMemoryScope()


async def build_memory(
    config: MemoryConfig, clock: Clock
) -> tuple[MemoryRecaller | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config; return the recaller (or None) with its closer."""
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        scope = memory_scope_from_name(config.scope)
        return MemoryRecaller(store, embedder, clock, scope=scope), close_memory
    return None, noop_aclose


async def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009)."""
    if config.backend != "mcp":
        return None, noop_aclose
    stack = AsyncExitStack()
    registries: list[ToolRegistry] = []
    try:
        for name, url in config.named_endpoints.items():
            registry, close = await McpToolRegistry.connect(url)
            stack.push_async_callback(close)
            allow = config.allow.get(name)
            if allow:
                registry = FilteredToolRegistry(registry, allow=allow)
            if config.on_unavailable == "skip":
                registry = SkipUnavailableToolRegistry(
                    registry, name=name, report=_report_sidecar_unavailable
                )
            registries.append(registry)
    except BaseException:
        await stack.aclose()
        raise
    root = registries[0] if len(registries) == 1 else AggregateToolRegistry(registries)
    if config.gated:
        root = GatedToolRegistry(root, gated=config.gated)
    return root, stack.aclose


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


def build_cortex_tools(
    tool_registry: ToolRegistry | None,
    spawn_tool: SpawnSubagentsTool | None,
    clock: Clock,
    *,
    confirmer: Confirmer | None = None,
    gated_names: Collection[str] = (),
    body: BodyGateway | None = None,
) -> ToolDispatcher | None:
    """The cortex's audited dispatcher: the spawn + volume built-ins merged with the MCP tools."""
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if body is not None:
        builtins.append(GetVolumeTool(body))
        builtins.append(SetVolumeTool(body))
    if not builtins and tool_registry is None:
        return None
    registry = CompositeToolRegistry(builtins, remote=tool_registry)
    return ToolDispatcher(
        registry, LoggingAuditSink(), clock, confirmer=confirmer, gated_names=gated_names
    )
