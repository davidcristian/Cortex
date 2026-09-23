"""Subagent wiring: the roster, the runner, and the spawn tool from config."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    Clock,
    ConfirmFreeToolRegistry,
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
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.builders import build_generation_client, noop_aclose
from cortex_orchestrator.config_subagents import SubagentRosterEntry, SubagentsConfig
from cortex_orchestrator.dispatch_builders import DEFAULT_DISPATCH_SETUP, DispatchSetup
from cortex_session import RedisTaskStore


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
) -> tuple[SpawnSubagentsTool | None, SubagentScheduler | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled."""
    if config.backend == "none":
        return None, None, noop_aclose
    client = build_generation_client(config.stall_timeout_s)
    scheduler = ResourceBudgetScheduler(
        config.cpu_budget, config.mem_budget_gb, wait_timeout_s=config.admission_wait_s
    )
    roster = SubagentRoster(
        entries={
            name: _entry_profile(name, entry, client, scheduler, placer)
            for name, entry in config.named_roster.items()
        },
        default=config.model,
    )
    store = task_store_factory(redis_url)
    runner = SubagentRunner(
        store,
        roster,
        clock,
        tools=tools,
        constrain_output=config.constrain_output,
        bounds=config.attempt_bounds,
    )

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()

    return SpawnSubagentsTool(runner, store, clock), scheduler, close_subagents


def build_subagent_tools(
    tool_registry: ToolRegistry | None,
    clock: Clock,
    *,
    setup: DispatchSetup = DEFAULT_DISPATCH_SETUP,
) -> ToolDispatcher | None:
    """A subagent's audited dispatcher over the MCP subset it may call, or None."""
    if tool_registry is None:
        return None
    return ToolDispatcher(
        ConfirmFreeToolRegistry(tool_registry),
        setup.audit,
        clock,
        policy=setup.policy,
    )
