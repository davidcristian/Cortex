"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable

from cortex_core import Confirmer, SystemClock, TurnCapabilities, TurnEngine, VramBudgetPlacer
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
    ToolsConfig,
)
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
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
    """Compose the brain from the environment and serve until shutdown."""
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
    memory, close_memory = await build_memory(memory_config, clock)
    tool_registry, close_tools = build_tool_registry(tools_config)
    body, close_body = await build_body_gateway(body_config, token=seam_config.token)
    # The subagent dispatcher is assembled here so the user's gated-name backstop
    # (CORTEX_TOOLS_GATED) covers subagents too, composing with the UngatedToolRegistry
    # strip inside build_subagent_tools (ADR-0022).
    spawn_tool, close_subagents = await build_subagents(
        subagents_config,
        build_subagent_tools(tool_registry, clock, gated_names=tools_config.gated),
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
        gated_names=tools_config.gated,
    )
    ticker_task = start_ticker(ticker)
    try:

        def make_engine(confirmer: Confirmer) -> TurnEngine:
            # One engine per Converse stream (ADR-0022): the stream's confirmer reaches the
            # dispatcher, and everything else is the same shared adapters. Engines are
            # stateless functions over the store, so per-stream construction costs nothing.
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
                        gated_names=tools_config.gated,
                    ),
                    window=build_history_window(runtime.history_char_budget),
                    guardrail=build_output_guardrail(runtime.output_guardrail),
                    # The core takes a bool; the composition root maps the string (ADR-0019).
                    record_tainted_memory=memory_config.on_tainted == "record",
                ),
            )

        await serve(seam_config, make_engine, store, schedules=schedules)
    finally:
        await stop_ticker(ticker, ticker_task)
        await close_schedules()
        await close_body()
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
