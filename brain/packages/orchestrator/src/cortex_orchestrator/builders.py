"""Adapter builders for the composition root: pick each port's adapter from config.

One builder per capability, called only by `wiring.run_from_env` (DI at the edge,
AGENTS.md). Each returns the built dependency together with the coroutine that
releases it, so the root's shutdown path is uniform whatever was picked:

- InferenceBackend -> `EchoInferenceBackend` by default (GPU-less), or the real
  `LlamaCppBackend` over a `SingleResidentModelManager` when CORTEX_INFERENCE_BACKEND
  is `llamacpp` (ADR-0007). The GPU path is opt-in so CI stays inference-free.
- Memory -> disabled by default, or a `MemoryRecaller` over the `PgVectorMemoryStore` +
  `LlamaCppEmbedder` when CORTEX_MEMORY_BACKEND is `pgvector` (ADR-0008). Opt-in so CI and
  the no-GPU dev loop stay DB-free.
- Tools -> the MCP `ToolRegistry` when CORTEX_TOOLS_BACKEND is `mcp` (ADR-0009), else None:
  one client per configured endpoint, allowlist-filtered, optionally skip-unavailable
  (degraded-mode addendum), and aggregated as configured. Shared by the cortex (via the
  composite) and its subagents.
- Subagents -> `subagent_builders.py` (split for the 300-line cap when the ADR-0018 roster
  arrived): the `spawn_subagents` tool over a roster-resolving `SubagentRunner`.
- History window -> `CharBudgetHistoryWindow` over CORTEX_HISTORY_CHAR_BUDGET (ADR-0014),
  on by default (48K chars ≈ 12K of the cortex's 16K-token context); 0 disables it.
- Output guardrail -> `UrlRedactingGuardrail` over CORTEX_OUTPUT_GUARDRAIL (ADR-0015), on by
  default (hardening ships enabled); `off` restores the unguarded stream.
"""

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
    SingleResidentModelManager,
    SkipUnavailableToolRegistry,
    SpawnSubagentsTool,
    ToolDispatcher,
    ToolError,
    ToolRegistry,
    UrlRedactingGuardrail,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_inference import LlamaCppBackend
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.config import InferenceConfig, MemoryConfig, ToolsConfig
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
    return None, noop_aclose


async def build_tool_registry(
    config: ToolsConfig,
) -> tuple[ToolRegistry | None, Callable[[], Awaitable[None]]]:
    """The raw MCP `ToolRegistry` shared by the cortex and its subagents, or None (ADR-0009).

    ``none`` disables tools. The MCP-less default CI and the no-GPU dev loop run. ``mcp``
    connects one MCP client per configured endpoint (refinements addendum): an endpoint with
    an allowlist is wrapped in `FilteredToolRegistry`, and several endpoints merge behind one
    `AggregateToolRegistry` (first-wins by the config's sorted-name order). With
    `CORTEX_TOOLS_ON_UNAVAILABLE=skip` each endpoint is additionally wrapped in
    `SkipUnavailableToolRegistry` (degraded-mode addendum): a sidecar dead at listing time is
    logged and served around instead of failing the whole tool set. Note this covers a
    sidecar dying *after* connect; a sidecar down *at startup* still fails `connect` here.
    The returned closer releases every session; a failed later connect unwinds the earlier
    ones. The registry is left un-audited here. The cortex and each subagent wrap it in
    their own `ToolDispatcher`.
    """
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
    if len(registries) == 1:
        return registries[0], stack.aclose
    return AggregateToolRegistry(registries), stack.aclose


def build_output_guardrail(mode: str) -> UrlRedactingGuardrail | None:
    """The turn's output guardrail, or None when disabled (ADR-0015).

    `redact` (`CORTEX_OUTPUT_GUARDRAIL`'s default, so hardening is on out of the box) scrubs
    URLs sourced from untrusted tool results out of the reply the user sees, the
    model-independent laundering defense; `off` restores the unguarded stream. A clean turn
    is untouched either way (nothing collected, nothing scrubbed).
    """
    return UrlRedactingGuardrail() if mode == "redact" else None


def build_history_window(char_budget: int) -> CharBudgetHistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014).

    A positive budget caps what one turn sends to the model at the newest whole turns
    fitting it; 0 (`CORTEX_HISTORY_CHAR_BUDGET=0`) disables windowing, so the model gets
    the full stored history, the pre-ADR-0014 behavior. Persistence is untouched either way.
    """
    return CharBudgetHistoryWindow(char_budget) if char_budget > 0 else None


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
