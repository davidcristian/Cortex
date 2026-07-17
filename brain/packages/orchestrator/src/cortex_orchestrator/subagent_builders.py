"""Subagent wiring: the roster, the runner, and the spawn tool from config (ADR-0010/0012/0018).

Split from `builders.py` when the ADR-0018 roster arrived (the 300-line cap); the contract is
the same. Builders are called only by `wiring.run_from_env`, each returning the dependency plus the
coroutine that releases it.

Delegation is disabled by default (CI and the no-GPU dev loop run subagent-free). With
`CORTEX_SUBAGENTS_BACKEND=llamacpp` the cortex gets the `spawn_subagents` tool over a
`SubagentRunner` that resolves each spawn against the **roster** built here (ADR-0018): the
default entry from the flat env, the injection-robust ADR-0004 pick every untrusted-content
spawn is pinned to (ADR-0017), plus one alternate per `CORTEX_SUBAGENTS_ROSTER__<name>`. Each
entry gets its own backend pair (GPU + CPU `llama-server` endpoints behind one shared HTTP
client) and its own `PlacementRequest`; the `ResourceBudgetScheduler` and the `SubagentPlacer`
are ONE object across entries, meaning one CPU/RAM budget, one VRAM ledger, whatever the mix
(ADR-0012 unchanged). A subagent runs the shared tool loop with the MCP tool subset (no
delegation, so depth-1), stripped of gated tools by `UngatedToolRegistry` (ADR-0013
subagent-exclusion addendum), as a stateless function over the Redis `TaskStore`. The
dispatcher over that subset arrives pre-assembled from `build_subagent_tools` at the
composition root (the builtins-bundling precedent for the argument ceiling), which threads
`CORTEX_TOOLS_GATED` in as the authoritative gated-name backstop (ADR-0022).
"""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    DEFAULT_DISPATCH_POLICY,
    Clock,
    DispatchPolicy,
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
) -> tuple[SpawnSubagentsTool | None, SubagentScheduler | None, Callable[[], Awaitable[None]]]:
    """The `spawn_subagents` tool, or None when delegation is disabled (ADR-0010/0012/0018).

    Enabled: `config.named_roster` becomes a `SubagentRoster` holding the flat-env default entry
    (`config.model`, the robust pick) plus the configured alternates, and the runner resolves
    every spawn against it (the ADR-0017 boundary lives in the core, not here). Placement is
    GPU-first per entry: the shared `placer` (built from the GPU soft cap at the call site)
    fit-tests each spawn, routing to that entry's GPU `llama-server` (`-ngl 99`) or its CPU one
    (`-ngl 0`); the shared `ResourceBudgetScheduler` admits it under one soft CPU/RAM budget.
    `tools` is the subagents' dispatcher, pre-assembled by `build_subagent_tools` at the
    composition root so the user's `CORTEX_TOOLS_GATED` backstop reaches it without a
    seventh builder argument (ADR-0022). `config.constrain_output` (default on) rides onto the
    runner, so a tool-less subagent's reply is decoded into the fixed envelope (ADR-0028). The
    returned closer releases the shared backend client and the task store; the shared MCP
    session is released by `build_tool_registry`, not here.

    The scheduler is returned alongside the tool because the swap conductor has to quiesce this
    very pool before a model handoff evicts anything (ADR-0030 decision 4): one budget object,
    composed at the root, never a second one that would admit past the drain.
    """
    if config.backend == "none":
        return None, None, noop_aclose
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
    runner = SubagentRunner(
        store, roster, clock, tools=tools, constrain_output=config.constrain_output
    )

    async def close_subagents() -> None:
        await store.aclose()
        await client.aclose()

    return SpawnSubagentsTool(runner, store, clock), scheduler, close_subagents


def build_subagent_tools(
    tool_registry: ToolRegistry | None,
    clock: Clock,
    *,
    policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
) -> ToolDispatcher | None:
    """A subagent's audited dispatcher over the gated-stripped MCP subset, or None (ADR-0013).

    A subagent is never *handed* an outbound/gated tool (subagent-exclusion addendum):
    `UngatedToolRegistry` strips gated specs from advertisement and refuses invoking them, so
    a gated tool added to the shared registry later simply does not exist for a subagent. There is
    nothing dangerous to call, not merely denied at the fail-closed gate (its dispatcher also
    keeps the `confirmer=None` default). The spawn tool is likewise absent (depth-1, ADR-0010).
    The policy's `gated_names` is the authoritative gate backstop (ADR-0022): should the skip-mode
    advertisement window ever let a stripped-then-recovered gated name through, the dispatcher
    still treats it as gated, and with `confirmer=None` that is a hard deny. The composition
    root passes `CORTEX_TOOLS_GATED` here, so the user's set covers subagents too.

    The policy's `costs` (`CORTEX_TOOLS_COSTS`) is threaded for the same reason: an MCP tool a
    user priced is priced in delegated work as well, which is where it matters most, since
    fan-out is exactly what multiplies a cheap-looking call. Its `salience` reaches subagents the
    same way, and the per-loop scoping means a subagent's repeats are counted against its own
    rounds, never against a sibling's, which is the point (ADR-0009 salience addendum): siblings
    hold different message lists, so a read one of them already made is new to the others.
    """
    if tool_registry is None:
        return None
    return ToolDispatcher(
        UngatedToolRegistry(tool_registry),
        LoggingAuditSink(),
        clock,
        policy=policy,
    )
