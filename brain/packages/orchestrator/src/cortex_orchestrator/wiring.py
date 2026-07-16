"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md).
The per-capability builders live in `builders.py` (and `subagent_builders.py` for
delegation, `memory_builders.py` for recall), one per port, each returning the dependency
plus its closer; this module only reads the env configs, calls them, hands the `TurnEngine`
its ports, and releases everything on the way out:

- SessionStore  -> `RedisSessionStore` over CORTEX_REDIS_URL, holding the state that
  survives restarts and model swaps (the one hard rule).
- Clock -> `SystemClock`, shared by the turn engine, memory recaller, and
  tool/subagent audit.
- InferenceBackend / Memory / Tools / Subagents / History window / Output guardrail
  -> the builders (ADR-0007/0008/0009/0010/0012/0014/0015); every capability needing an
  external service is off by default so CI and the no-GPU dev loop run free of them
  (the pure guardrail, like the window, ships on).

Everything below the edge receives ports, never settings objects or env access.
"""

from collections.abc import Callable

from cortex_core import (
    Confirmer,
    ProgressSink,
    SystemClock,
    TurnCapabilities,
    TurnEngine,
    VramBudgetPlacer,
)
from cortex_orchestrator.builders import (
    build_body_gateway,
    build_builtin_tools,
    build_cortex_tools,
    build_history_window,
    build_inference_backend,
    build_output_guardrail,
    build_tool_registry,
)
from cortex_orchestrator.config import (
    BodyConfig,
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
)
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.memory_builders import build_memory
from cortex_orchestrator.schedule_builders import (
    build_schedule,
    build_schedule_tools,
    build_ticker,
    start_ticker,
    stop_ticker,
)
from cortex_orchestrator.server import serve
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_session import RedisSessionStore


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
    body_config = BodyConfig()
    subagents_config = SubagentsConfig()
    schedule_config = ScheduleConfig()
    clock = SystemClock()
    store = store_factory(runtime.redis_url)
    backend, close_backend = build_inference_backend(inference, runtime.cortex_model)
    memory, memory_cascade, close_memory = await build_memory(memory_config, clock)
    tool_registry, close_tools = build_tool_registry(tools_config)
    body, close_body = await build_body_gateway(body_config, token=seam_config.token)
    # The subagent dispatcher is assembled here so the user's gated-name backstop
    # (CORTEX_TOOLS_GATED) covers subagents too, composing with the UngatedToolRegistry
    # strip inside build_subagent_tools (ADR-0022), and so the tool prices
    # (CORTEX_TOOLS_COSTS) charge delegated work at the same rate (ADR-0009 cost addendum) and
    # the salience rule (CORTEX_TOOLS_SALIENCE) refuses a delegate's repeats the way it refuses
    # the cortex's, each against its own rounds (ADR-0009 salience addendum). One policy value
    # carries all three, which is also what keeps these builders under the argument ceiling.
    spawn_tool, close_subagents = await build_subagents(
        subagents_config,
        build_subagent_tools(
            tool_registry,
            clock,
            policy=tools_config.dispatch_policy,
        ),
        runtime.redis_url,
        clock,
        placer=VramBudgetPlacer(
            soft_cap_gb=runtime.vram_soft_cap_gb,
            cortex_reservation_gb=runtime.cortex_reservation_gb,
        ),
    )
    schedules, close_schedules = build_schedule(schedule_config, runtime.redis_url)
    # The built-in set is confirmer-independent, so it is assembled once (ADR-0025 d7);
    # the ticker fires beside `serve` and is stopped before its store closes.
    builtins = build_builtin_tools(
        spawn_tool,
        body,
        schedule_tools=build_schedule_tools(
            schedule_config, schedules, clock, tasks_enabled=spawn_tool is not None
        ),
    )
    ticker = build_ticker(
        schedule_config,
        schedules,
        clock,
        spawn_tool=spawn_tool,
        body=body,
        policy=tools_config.dispatch_policy,
    )
    ticker_task = start_ticker(ticker)
    try:

        def make_engine(confirmer: Confirmer, progress: ProgressSink) -> TurnEngine:
            # One engine per Converse stream (ADR-0022/0010): the stream's confirmer reaches the
            # dispatcher and its progress sink reaches the turn (so a spawned subagent surfaces
            # onto this stream's overlay), and everything else is the same shared adapters.
            # Engines are stateless functions over the store, so per-stream construction is free.
            return TurnEngine(
                store,
                backend,
                clock,
                cortex_model=runtime.cortex_model,
                capabilities=TurnCapabilities(
                    memory=memory,
                    tools=build_cortex_tools(
                        tool_registry,
                        builtins,
                        clock,
                        confirmer=confirmer,
                        policy=tools_config.dispatch_policy,
                    ),
                    window=build_history_window(runtime.history_char_budget),
                    guardrail=build_output_guardrail(runtime.output_guardrail),
                    # The core takes a bool; the composition root maps the string (ADR-0019).
                    record_tainted_memory=memory_config.on_tainted == "record",
                    generate_titles=runtime.generate_titles,
                    progress=progress,
                ),
            )

        await serve(
            seam_config, make_engine, store, schedules=schedules, memory_cascade=memory_cascade
        )
    finally:
        await stop_ticker(ticker, ticker_task)
        await close_schedules()
        await close_body()
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
