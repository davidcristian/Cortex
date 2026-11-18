"""Subagent wiring: the roster, the runner, and the spawn tool from config."""

from collections.abc import Awaitable, Callable, Mapping

import httpx

from cortex_core import (
    NO_ROLES,
    SERVING_CHECK_TIMEOUT_S,
    SHIPPED_ROLES,
    Clock,
    ConfirmFreeToolRegistry,
    ModelServer,
    MultiServerModelManager,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    ServingProbe,
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
from cortex_inference import LlamaCppBackend, LlamaServerProbe, gpu_server_wording
from cortex_orchestrator.builders import build_generation_client, noop_aclose
from cortex_orchestrator.config_subagents import (
    SubagentRosterEntry,
    SubagentsConfig,
    endpoint_list,
)
from cortex_orchestrator.dispatch_builders import DEFAULT_DISPATCH_SETUP, DispatchSetup
from cortex_session import RedisTaskStore


def _backend(
    name: str,
    endpoints: tuple[str, ...],
    slots: int,
    client: httpx.AsyncClient,
    probe: Callable[[str], ServingProbe | None],
) -> LlamaCppBackend:
    """One backend over every server a placement target names, each with ``slots`` slots."""
    servers = [ModelServer(endpoint, slots, probe(endpoint)) for endpoint in endpoints]
    return LlamaCppBackend(MultiServerModelManager(name, servers), client)


def _unasked(endpoint: str) -> None:
    """No probe: a CPU server is the last target, so its own request reports what it does."""
    del endpoint


def _entry_profile(  # noqa: PLR0913 -- one entry, the two shared budgets and the two shared clients
    name: str,
    entry: SubagentRosterEntry,
    client: httpx.AsyncClient,
    health: httpx.AsyncBaseTransport,
    scheduler: SubagentScheduler,
    placer: SubagentPlacer,
    slots: Mapping[PlacementTarget, int],
) -> SubagentProfile:
    """One roster entry's runtime profile: its own servers and ask, the shared budgets."""

    def asked(endpoint: str) -> ServingProbe:
        """The probe a GPU server is asked through before each lease of it."""
        return LlamaServerProbe(
            endpoint,
            health,
            timeout_s=SERVING_CHECK_TIMEOUT_S,
            wording=gpu_server_wording(name, endpoint),
        )

    on_cpu, on_gpu = endpoint_list(entry.endpoint), endpoint_list(entry.gpu_endpoint)
    cpu = _backend(name, on_cpu, slots[PlacementTarget.CPU], client, _unasked)
    # Two targets naming the same servers share one backend, so a slot is leased once.
    gpu = (
        cpu
        if on_gpu == on_cpu
        else _backend(name, on_gpu, slots[PlacementTarget.GPU], client, asked)
    )
    return SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: gpu, PlacementTarget.CPU: cpu},
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
    health = httpx.AsyncHTTPTransport()
    scheduler = ResourceBudgetScheduler(
        config.cpu_budget, config.mem_budget_gb, wait_timeout_s=config.admission_wait_s
    )
    slots = {PlacementTarget.GPU: config.gpu_parallel, PlacementTarget.CPU: config.parallel}
    roster = SubagentRoster(
        entries={
            name: _entry_profile(name, entry, client, health, scheduler, placer, slots)
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
        roles=SHIPPED_ROLES if config.roles else NO_ROLES,
    )

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()
        await health.aclose()

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
