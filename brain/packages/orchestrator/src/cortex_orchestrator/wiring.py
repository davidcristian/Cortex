"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    BuiltinTool,
    Clock,
    CompositeToolRegistry,
    ConcurrencyScheduler,
    EchoInferenceBackend,
    InferenceBackend,
    MemoryRecaller,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    SubagentRunner,
    SystemClock,
    ToolDispatcher,
    ToolRegistry,
    TurnCapabilities,
    TurnEngine,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    SubagentsConfig,
    ToolsConfig,
)
from cortex_orchestrator.server import serve
from cortex_session import RedisSessionStore, RedisTaskStore
from cortex_tools import LoggingAuditSink, McpToolRegistry

# Connect/write/pool time out fast on a dead server; reads have no deadline, since a
# generation may legitimately stream for a long time (the adapter sets no timeout itself).
_LLAMACPP_CONNECT_TIMEOUT_S = 10.0
# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0


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
    if config.backend == "mcp":
        registry, close = await McpToolRegistry.connect(config.endpoint)
        return registry, close
    return None, _noop_aclose


async def build_subagents(
    config: SubagentsConfig,
    tool_registry: ToolRegistry | None,
    redis_url: str,
    clock: Clock,
    *,
    task_store_factory: Callable[[str], RedisTaskStore] = RedisTaskStore.from_url,
) -> tuple[SpawnSubagentsTool | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled (ADR-0010)."""
    if config.backend == "none":
        return None, _noop_aclose
    client = httpx.AsyncClient(timeout=httpx.Timeout(_LLAMACPP_CONNECT_TIMEOUT_S, read=None))
    manager = SingleResidentModelManager(config.model, config.endpoint)
    store = task_store_factory(redis_url)
    subagent_tools = (
        ToolDispatcher(tool_registry, LoggingAuditSink(), clock)
        if tool_registry is not None
        else None
    )
    runner = SubagentRunner(
        store,
        LlamaCppBackend(manager, client),
        ConcurrencyScheduler(config.max_concurrency),
        clock,
        subagent_model=config.model,
        tools=subagent_tools,
    )

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()

    return SpawnSubagentsTool(runner, store, clock), close_subagents


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


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown."""
    seam_config = SeamServerConfig()
    runtime = BrainRuntimeConfig()
    inference = InferenceConfig()
    memory_config = MemoryConfig()
    tools_config = ToolsConfig()
    subagents_config = SubagentsConfig()
    clock = SystemClock()
    store = store_factory(runtime.redis_url)
    backend, close_backend = build_inference_backend(inference, runtime.cortex_model)
    memory, close_memory = await build_memory(memory_config, clock)
    tool_registry, close_tools = await build_tool_registry(tools_config)
    spawn_tool, close_subagents = await build_subagents(
        subagents_config, tool_registry, runtime.redis_url, clock
    )
    tools = build_cortex_tools(tool_registry, spawn_tool, clock)
    try:
        engine = TurnEngine(
            store,
            backend,
            clock,
            cortex_model=runtime.cortex_model,
            capabilities=TurnCapabilities(memory=memory, tools=tools),
        )
        await serve(seam_config, engine)
    finally:
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
