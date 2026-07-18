"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable
from dataclasses import replace

from cortex_core import (
    AsyncioSleeper,
    BrainPhase,
    CaptureBounds,
    Confirmer,
    EscalatingTurnEngine,
    ProgressSink,
    SwapConductor,
    SystemClock,
    TurnCapabilities,
    TurnEngine,
    TurnRunner,
    VramBudgetPlacer,
    recover_handoffs,
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
from cortex_orchestrator.config_swap import SwapConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.memory_builders import build_memory
from cortex_orchestrator.schedule_builders import (
    build_schedule,
    build_schedule_tools,
    build_ticker,
    start_ticker,
    stop_ticker,
)
from cortex_orchestrator.server import SeamPorts, serve
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.swap_builders import build_swap_runtime, swap_closer
from cortex_orchestrator.vision import vision_enabled
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
    swap_config = SwapConfig()
    clock = SystemClock()
    store = store_factory(runtime.redis_url)
    swap = build_swap_runtime(swap_config, runtime, inference, clock, AsyncioSleeper())
    backend, close_backend = build_inference_backend(
        inference, runtime.cortex_model, manager=None if swap is None else swap.manager
    )
    memory, memory_cascade, close_memory = await build_memory(memory_config, clock)
    tool_registry, close_tools = build_tool_registry(tools_config)
    body, close_body = await build_body_gateway(body_config, token=seam_config.token)
    spawn_tool, scheduler, close_subagents = await build_subagents(
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
    capture = (
        CaptureBounds(max_edge=body_config.capture_max_edge, max_bytes=body_config.max_image_bytes)
        if body is not None and await vision_enabled(inference.vision, inference.endpoint)
        else None
    )
    builtins = build_builtin_tools(
        spawn_tool,
        body,
        schedule_tools=build_schedule_tools(
            schedule_config, schedules, clock, tasks_enabled=spawn_tool is not None
        ),
        escalation=swap is not None,
        vision=capture,
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
    if swap is not None:
        converged = await recover_handoffs(
            swap.handoffs, swap.host, swap.plan, clock=clock, sleeper=AsyncioSleeper()
        )
        await swap.manager.publish_boot_residency(serving=converged)
    try:

        def capabilities(confirmer: Confirmer, progress: ProgressSink) -> TurnCapabilities:
            return TurnCapabilities(
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
            )

        def make_turn_engine(caps: TurnCapabilities) -> TurnEngine:
            # Engines are stateless functions over the store, so per-stream (and, when a turn
            # escalates, per-turn) construction is free.
            return TurnEngine(
                store, backend, clock, cortex_model=runtime.cortex_model, capabilities=caps
            )

        def make_engine(confirmer: Confirmer, progress: ProgressSink) -> TurnRunner:
            caps = capabilities(confirmer, progress)
            if swap is None:
                return make_turn_engine(caps)
            conductor = SwapConductor(
                swap.handoffs,
                swap.manager,
                BrainPhase(
                    store, backend, clock, swap.plan.brain_model, replace(caps, escalation=None)
                ),
                swap.plan,
                clock,
                scheduler,
            )
            return EscalatingTurnEngine(
                lambda slot: make_turn_engine(replace(caps, escalation=slot)), conductor
            )

        await serve(
            seam_config,
            make_engine,
            store,
            SeamPorts(
                schedules=schedules,
                memory_cascade=memory_cascade,
                # The manager is the seam's residency reporter too (ADR-0030 decision 6): Health
                # reads it synchronously, so a probe between turns says what the GPU is really
                # doing. Absent with escalation off, where nothing can make the brain not-ready.
                residency=None if swap is None else swap.manager,
            ),
        )
    finally:
        await stop_ticker(ticker, ticker_task)
        await swap_closer(swap)()
        await close_schedules()
        await close_body()
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await store.aclose()
