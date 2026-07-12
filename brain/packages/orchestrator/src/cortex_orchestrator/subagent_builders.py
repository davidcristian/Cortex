"""Subagent wiring: the roster, the runner, and the spawn tool from config (ADR-0010/0012/0018)."""

from collections.abc import Awaitable, Callable, Collection

import httpx

from cortex_core import (
    Clock,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    SubagentPlacer,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SubagentScheduler,
    ToolDispatcher,
    ToolRegistry,
    UngatedToolRegistry,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.builders import LLAMACPP_CONNECT_TIMEOUT_S, noop_aclose
from cortex_orchestrator.config_subagents import SubagentRosterEntry, SubagentsConfig
from cortex_session import RedisTaskStore
from cortex_tools import LoggingAuditSink


def _entry_profile(
    name: str,
    entry: SubagentRosterEntry,
    client: httpx.AsyncClient,
    scheduler: SubagentScheduler,
    placer: SubagentPlacer,
) -> SubagentProfile:
    """One roster entry's runtime profile: its own backend pair + ask, the shared budgets."""
    return SubagentProfile(
        resources=SubagentResources(
            backends={
                PlacementTarget.GPU: LlamaCppBackend(
                    SingleResidentModelManager(name, entry.gpu_endpoint), client
                ),
                PlacementTarget.CPU: LlamaCppBackend(
                    SingleResidentModelManager(name, entry.endpoint), client
                ),
            },
            scheduler=scheduler,
            placer=placer,
            request=PlacementRequest(name, entry.vram_gb, entry.cpus, entry.memory_gb),
        ),
        description=entry.description,
    )


async def build_subagents(
    config: SubagentsConfig,
    tools: ToolDispatcher | None,
    redis_url: str,
    clock: Clock,
    *,
    placer: SubagentPlacer,
    task_store_factory: Callable[[str], RedisTaskStore] = RedisTaskStore.from_url,
) -> tuple[SpawnSubagentsTool | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled (ADR-0010/0012/0018)."""
    if config.backend == "none":
        return None, noop_aclose
    client = httpx.AsyncClient(timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None))
    scheduler = ResourceBudgetScheduler(config.cpu_budget, config.mem_budget_gb)
    roster = SubagentRoster(
        entries={
            name: _entry_profile(name, entry, client, scheduler, placer)
            for name, entry in config.named_roster.items()
        },
        default=config.model,
    )
    store = task_store_factory(redis_url)
    runner = SubagentRunner(store, roster, clock, tools=tools)

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()

    return SpawnSubagentsTool(runner, store, clock), close_subagents


def build_subagent_tools(
    tool_registry: ToolRegistry | None, clock: Clock, *, gated_names: Collection[str] = ()
) -> ToolDispatcher | None:
    """A subagent's audited dispatcher over the gated-stripped MCP subset, or None (ADR-0013)."""
    if tool_registry is None:
        return None
    return ToolDispatcher(
        UngatedToolRegistry(tool_registry), LoggingAuditSink(), clock, gated_names=gated_names
    )
