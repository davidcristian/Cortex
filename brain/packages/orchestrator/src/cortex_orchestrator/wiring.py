"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable

from cortex_core import SystemClock, TurnCapabilities, TurnEngine, VramBudgetPlacer
from cortex_orchestrator.builders import (
    build_cortex_tools,
    build_history_window,
    build_inference_backend,
    build_memory,
    build_output_guardrail,
    build_tool_registry,
)
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    SubagentsConfig,
    ToolsConfig,
)
from cortex_orchestrator.server import serve
from cortex_orchestrator.subagent_builders import build_subagents
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
            capabilities=TurnCapabilities(
                memory=memory,
                tools=tools,
                window=build_history_window(runtime.history_char_budget),
                guardrail=build_output_guardrail(runtime.output_guardrail),
                # The core takes a bool; the composition root maps the string (ADR-0019).
                record_tainted_memory=memory_config.on_tainted == "record",
            ),
        )
        await serve(seam_config, engine, store)
    finally:
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
