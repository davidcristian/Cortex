"""Adapter builders for the composition root: pick each port's adapter from config."""

import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack

import httpx

from cortex_core import (
    AggregateToolRegistry,
    BuiltinTool,
    CharBudgetHistoryWindow,
    Clock,
    CompositeToolRegistry,
    EchoInferenceBackend,
    FilteredToolRegistry,
    InferenceBackend,
    MemoryRecaller,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    SpawnSubagentsTool,
    SubagentPlacer,
    SubagentResources,
    SubagentRunner,
    ToolDispatcher,
    ToolError,
    ToolRegistry,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.config import (
    InferenceConfig,
    MemoryConfig,
    SubagentsConfig,
    ToolsConfig,
)
from cortex_session import RedisTaskStore
from cortex_tools import LoggingAuditSink, McpToolRegistry

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
_LLAMACPP_CONNECT_TIMEOUT_S = 10.0
# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0

_logger = logging.getLogger(__name__)


def _report_sidecar_unavailable(name: str, error: ToolError) -> None:
    """The skip-and-report reporter: degradation is a logged warning, never silent."""
    _logger.warning(
        "tool sidecar unavailable; serving without it",
        extra={"sidecar": name, "error": str(error)},
    )


async def _noop_aclose() -> None:
    """Echo holds no resources; the default backend has nothing to release."""
    return


def build_inference_backend(
    config: InferenceConfig, cortex_model: str
) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]:
    """Pick the backend from config; return it with the coroutine that releases it.

    Returns the no-op closer for Echo (no resources) and the HTTP client's ``aclose`` for
    llama.cpp, so the caller's shutdown path is uniform regardless of which backend ran.
    """
    if config.backend == "llamacpp":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_LLAMACPP_CONNECT_TIMEOUT_S, read=None))
        manager = SingleResidentModelManager(cortex_model, config.endpoint)
        return LlamaCppBackend(manager, client), client.aclose
    return EchoInferenceBackend(), _noop_aclose


async def build_memory(
    config: MemoryConfig, clock: Clock
) -> tuple[MemoryRecaller | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config; return the recaller (or None) with its closer.

    ``none`` disables memory. The DB-less default CI and the no-GPU dev loop run. ``pgvector``
    connects an asyncpg pool and a CPU embedder client; the returned closer releases both.
    """
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        return MemoryRecaller(store, embedder, clock), close_memory
    return None, _noop_aclose


async def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009)."""
    if config.backend != "mcp":
        return None, _noop_aclose
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
    if len(registries) == 1:
        return registries[0], stack.aclose
    return AggregateToolRegistry(registries), stack.aclose


async def build_subagents(
    config: SubagentsConfig,
    tool_registry: ToolRegistry | None,
    redis_url: str,
    clock: Clock,
    *,
    placer: SubagentPlacer,
    task_store_factory: Callable[[str], RedisTaskStore] = RedisTaskStore.from_url,
) -> tuple[SpawnSubagentsTool | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled (ADR-0010, ADR-0012)."""
    if config.backend == "none":
        return None, _noop_aclose
    client = httpx.AsyncClient(timeout=httpx.Timeout(_LLAMACPP_CONNECT_TIMEOUT_S, read=None))
    resources = SubagentResources(
        backends={
            PlacementTarget.GPU: LlamaCppBackend(
                SingleResidentModelManager(config.model, config.gpu_endpoint), client
            ),
            PlacementTarget.CPU: LlamaCppBackend(
                SingleResidentModelManager(config.model, config.endpoint), client
            ),
        },
        scheduler=ResourceBudgetScheduler(config.cpu_budget, config.mem_budget_gb),
        placer=placer,
        request=PlacementRequest(config.model, config.vram_gb, config.cpus, config.memory_gb),
    )
    store = task_store_factory(redis_url)
    subagent_tools = (
        ToolDispatcher(tool_registry, LoggingAuditSink(), clock)
        if tool_registry is not None
        else None
    )
    runner = SubagentRunner(store, resources, clock, tools=subagent_tools)

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()

    return SpawnSubagentsTool(runner, store, clock), close_subagents


def build_history_window(char_budget: int) -> CharBudgetHistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014)."""
    return CharBudgetHistoryWindow(char_budget) if char_budget > 0 else None


def build_cortex_tools(
    tool_registry: ToolRegistry | None,
    spawn_tool: SpawnSubagentsTool | None,
    clock: Clock,
) -> ToolDispatcher | None:
    """The cortex's audited dispatcher: the spawn tool merged with the MCP tools (ADR-0010)."""
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if not builtins and tool_registry is None:
        return None
    registry = CompositeToolRegistry(builtins, remote=tool_registry)
    return ToolDispatcher(registry, LoggingAuditSink(), clock)
