"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable
from dataclasses import replace

from cortex_core import (
    AsyncioSleeper,
    BrainPhase,
    CadenceTerms,
    Confirmer,
    EscalatingTurnEngine,
    ProgressSink,
    SwapConductor,
    SystemClock,
    TurnCapabilities,
    TurnEngine,
    TurnRunner,
    VramBudgetPlacer,
)
from cortex_orchestrator.bounds import check_tool_call_deadline
from cortex_orchestrator.builders import (
    build_body_gateway,
    build_builtin_tools,
    build_cortex_tools,
    build_inference_backend,
    build_output_guardrail,
    build_tool_registry,
)
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
)
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_reply import ReplyBoundsConfig
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
from cortex_orchestrator.stores import RedisStores
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.swap_builders import (
    build_swap_runtime,
    check_control_deadline,
    recover_boot_residency,
    swap_closer,
)
from cortex_orchestrator.vision import build_vision
from cortex_orchestrator.window_builders import build_history_window
from cortex_session import RedisPreferenceStore, RedisSessionStore


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
    preference_factory: Callable[[str], RedisPreferenceStore] = RedisPreferenceStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown."""
    seam_config = SeamServerConfig()
    runtime = BrainRuntimeConfig()
    inference = InferenceConfig()
    memory_config = MemoryConfig()
    tools_config = ToolsConfig()
    body_config = BodyConfig()
    subagents_config = check_tool_call_deadline(SubagentsConfig(), tools_config)
    schedule_config = ScheduleConfig()
    swap_config = SwapConfig()
    reply_bounds = ReplyBoundsConfig().bounds()
    clock = SystemClock()
    # The settings record rides the same Redis the conversation state does: durable for the same
    # reason (append-only + a named volume), so a choice outlives a body reinstall.
    stores = RedisStores.open(runtime.redis_url, store_factory, preference_factory)
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb,
        cortex_reservation_gb=runtime.cortex_reservation_gb,
    )
    swap = await check_control_deadline(
        build_swap_runtime(swap_config, runtime, inference, clock, AsyncioSleeper(), placer=placer)
    )
    backend, close_backend = build_inference_backend(
        inference, runtime.cortex_model, manager=None if swap is None else swap.manager
    )
    memory, memory_cascade, close_memory = await build_memory(
        memory_config, clock, backend, runtime.cortex_model
    )
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
        placer=placer,
    )
    schedules, close_schedules = build_schedule(schedule_config, runtime.redis_url)
    capture, sight, close_vision = build_vision(inference, body_config, body)
    schedule_tools = build_schedule_tools(
        schedule_config, schedules, clock, tasks_enabled=spawn_tool is not None
    )
    builtins = build_builtin_tools(
        spawn_tool,
        body,
        schedule_tools=schedule_tools,
        escalation=swap is not None,
        vision=capture,
    )
    deep_builtins = build_builtin_tools(
        spawn_tool,
        body,
        schedule_tools=schedule_tools,
        escalation=swap is not None,
        vision=None,
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
    # The handoff's other boot half, beside the deadline check and for the same reason: both are
    # swap wiring, and this file is at its line cap (`swap_builders.py`).
    await recover_boot_residency(swap, clock)
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
                    vision=sight,
                ),
                window=build_history_window(
                    runtime, sessions=stores.sessions, backend=backend, clock=clock
                ),
                guardrail=build_output_guardrail(runtime.output_guardrail),
                # The core takes a bool; the composition root maps the string (ADR-0019).
                record_tainted_memory=memory_config.on_tainted == "record",
                generate_titles=runtime.generate_titles,
                progress=progress,
                bounds=reply_bounds,
            )

        def make_turn_engine(caps: TurnCapabilities) -> TurnEngine:
            # Engines are stateless functions over the store, so per-stream (and, when a turn
            # escalates, per-turn) construction is free.
            return TurnEngine(
                stores.sessions,
                backend,
                clock,
                cortex_model=runtime.cortex_model,
                capabilities=caps,
            )

        def make_engine(confirmer: Confirmer, progress: ProgressSink) -> TurnRunner:
            caps = capabilities(confirmer, progress)
            if swap is None:
                return make_turn_engine(caps)
            deep = replace(
                caps,
                escalation=None,
                tools=build_cortex_tools(
                    tool_registry,
                    deep_builtins,
                    clock,
                    confirmer=confirmer,
                    policy=tools_config.dispatch_policy,
                ),
            )
            conductor = SwapConductor(
                swap.handoffs,
                swap.manager,
                BrainPhase(
                    stores.sessions,
                    backend,
                    clock,
                    swap.plan.brain_model,
                    deep,
                    CadenceTerms(swap.plan.brain_decode_tps, swap.manager.handoff_pace),
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
            stores.sessions,
            SeamPorts(
                schedules=schedules,
                memory_cascade=memory_cascade,
                # The manager is the seam's residency reporter too (ADR-0030 decision 6): Health
                # reads it synchronously, so a probe between turns says what the GPU is really
                # doing. Absent with escalation off, where nothing can make the brain not-ready.
                residency=None if swap is None else swap.manager,
                preferences=stores.preferences,
            ),
        )
    finally:
        await stop_ticker(ticker, ticker_task)
        await close_vision()
        await swap_closer(swap)()
        await close_schedules()
        await close_body()
        await close_subagents()
        await close_tools()
        await close_memory()
        await close_backend()
        await stores.aclose()
