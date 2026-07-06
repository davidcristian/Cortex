"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md).
The per-capability builders live in `builders.py` (and `subagent_builders.py` for
delegation), one per port, each returning the dependency plus its closer; this
module only reads the env configs, calls them, hands the `TurnEngine` its ports,
and releases everything on the way out:

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
            capabilities=TurnCapabilities(
                memory=memory,
                tools=tools,
                window=build_history_window(runtime.history_char_budget),
                guardrail=build_output_guardrail(runtime.output_guardrail),
                # The core takes a bool; the composition root maps the string (ADR-0019).
                record_tainted_memory=memory_config.on_tainted == "record",
            ),
        )
        await serve(seam_config, engine)
    finally:
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
