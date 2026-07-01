"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md):

- SessionStore  -> `RedisSessionStore` over CORTEX_REDIS_URL, holding the state that
  survives restarts and model swaps (the one hard rule).
- InferenceBackend -> `EchoInferenceBackend` by default (GPU-less), or the real
  `LlamaCppBackend` over a `SingleResidentModelManager` when CORTEX_INFERENCE_BACKEND
  is `llamacpp` (ADR-0007). The GPU path is opt-in so CI stays inference-free.
- Memory -> disabled by default, or a `MemoryRecaller` over the `PgVectorMemoryStore` +
  `LlamaCppEmbedder` when CORTEX_MEMORY_BACKEND is `pgvector` (ADR-0008). Opt-in so CI and
  the no-GPU dev loop stay DB-free.
- Tools -> the raw MCP `ToolRegistry` when CORTEX_TOOLS_BACKEND is `mcp` (ADR-0009), else None.
  Shared by the cortex (via the composite) and its subagents.
- Subagents -> disabled by default, or a `spawn_subagents` tool over a `SubagentRunner` (CPU
  `llama-server` + Redis `TaskStore` + concurrency budget) when CORTEX_SUBAGENTS_BACKEND is
  `llamacpp` (ADR-0010). The cortex's dispatcher merges the spawn tool with the MCP tools; a
  subagent gets the MCP tools without the spawn tool (depth-1). Opt-in so CI stays subagent-free.
- Clock -> `SystemClock`, shared by the turn engine, memory recaller, and tool/subagent audit.

Everything below the edge receives ports, never settings objects or env access.
"""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    BuiltinTool,
    Clock,
    CompositeToolRegistry,
    EchoInferenceBackend,
    InferenceBackend,
    MemoryRecaller,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    SubagentPlacer,
    SubagentResources,
    SubagentRunner,
    SystemClock,
    ToolDispatcher,
    ToolRegistry,
    TurnCapabilities,
    TurnEngine,
    VramBudgetPlacer,
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
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009).

    ``none`` disables tools. The MCP-less default CI and the no-GPU dev loop run. ``mcp`` connects
    the MCP client to the tool server; the returned closer releases that session. The registry is
    left un-audited here. The cortex and each subagent wrap it in their own `ToolDispatcher`.
    """
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
    placer: SubagentPlacer,
    task_store_factory: Callable[[str], RedisTaskStore] = RedisTaskStore.from_url,
) -> tuple[SpawnSubagentsTool | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled (ADR-0010, ADR-0012).

    Enabled (GPU-first, ADR-0012): the `placer` (built from the GPU soft cap at the call site)
    fit-tests each spawn, routing to the GPU `llama-server` (`-ngl 99`) or the CPU one (`-ngl 0`);
    the `ResourceBudgetScheduler` admits it under a soft CPU/RAM budget. A subagent runs the shared
    tool loop with the MCP tool subset (no delegation -- depth-1), as a stateless function over the
    Redis `TaskStore`. The returned closer releases the shared backend client and the task store;
    the shared MCP session is released by `build_tool_registry`, not here.
    """
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


def build_cortex_tools(
    tool_registry: ToolRegistry | None,
    spawn_tool: SpawnSubagentsTool | None,
    clock: Clock,
) -> ToolDispatcher | None:
    """The cortex's audited dispatcher: the spawn tool merged with the MCP tools (ADR-0010).

    None when neither is enabled (the Slice 3 turn path unchanged). The `CompositeToolRegistry`
    gives the built-in spawn tool precedence and advertises the MCP tools alongside it; subagents
    receive the MCP subset without the spawn tool (depth-1), wired in `build_subagents`.
    """
    builtins: list[BuiltinTool] = [spawn_tool] if spawn_tool is not None else []
    if not builtins and tool_registry is None:
        return None
    registry = CompositeToolRegistry(builtins, remote=tool_registry)
    return ToolDispatcher(registry, LoggingAuditSink(), clock)


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown.

    `store_factory` exists so tests can substitute a fakeredis-backed store; the
    production entrypoint always uses the default. The store's connections and every
    backend's resources are released on the way out, whatever ends `serve`.
    """
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
        subagents_config,
        tool_registry,
        runtime.redis_url,
        clock,
        placer=VramBudgetPlacer(
            soft_cap_gb=runtime.vram_soft_cap_gb,
            cortex_reservation_gb=runtime.cortex_reservation_gb,
        ),
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
