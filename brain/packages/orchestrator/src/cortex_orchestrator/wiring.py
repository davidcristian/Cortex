"""Composition root: build the runtime dependencies at the edge, then serve."""

from collections.abc import Callable

from cortex_core import AsyncioSleeper, SystemClock, VramBudgetPlacer
from cortex_orchestrator.bounds import check_tool_call_deadline
from cortex_orchestrator.builders import (
    build_body_gateway,
    build_builtin_tools,
    build_inference_backend,
    build_tool_registry,
)
from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    RpcServerConfig,
)
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_reply import ReplyBoundsConfig
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.dispatch_builders import DispatchSetup, tool_audit_from_config
from cortex_orchestrator.engines import DeepTier, StreamEngines
from cortex_orchestrator.memory_builders import build_memory
from cortex_orchestrator.schedule_builders import (
    build_schedule,
    build_schedule_tools,
    build_ticker,
    start_ticker,
    stop_ticker,
)
from cortex_orchestrator.server import RpcPorts, serve
from cortex_orchestrator.stores import RedisStores
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.swap_builders import (
    build_swap_runtime,
    check_control_deadline,
    recover_boot_residency,
    swap_closer,
)
from cortex_orchestrator.vision import build_vision
from cortex_session import RedisPreferenceStore, RedisSessionStore


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
    preference_factory: Callable[[str], RedisPreferenceStore] = RedisPreferenceStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown."""
    rpc_config = RpcServerConfig()
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
    stores = RedisStores.open(runtime.redis_url, store_factory, preference_factory)
    # One placer for the process: the subagent pool places against it, and the residency scope
    # tells it which model holds the GPU while a handoff runs, so the two must be one object.
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb,
        cortex_reservation_gb=runtime.cortex_reservation_gb,
    )
    swap = await check_control_deadline(
        build_swap_runtime(swap_config, runtime, inference, clock, AsyncioSleeper(), placer=placer)
    )
    backend, close_backend = await build_inference_backend(
        inference, runtime.cortex_model, manager=None if swap is None else swap.manager
    )
    memory, memory_cascade, close_memory = await build_memory(
        memory_config, clock, runtime.cortex_model
    )
    tool_registry, close_tools = build_tool_registry(tools_config)
    dispatch = DispatchSetup(tools_config.dispatch_policy, tool_audit_from_config(tools_config))
    body, close_body = await build_body_gateway(body_config, token=rpc_config.token)
    spawn_tool, scheduler, close_subagents = await build_subagents(
        subagents_config,
        build_subagent_tools(tool_registry, clock, setup=dispatch),
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
        setup=dispatch,
    )
    ticker_task = start_ticker(ticker)
    await recover_boot_residency(swap, clock)
    try:
        engines = StreamEngines(
            sessions=stores.sessions,
            backend=backend,
            clock=clock,
            runtime=runtime,
            memory=memory,
            tools=tool_registry,
            builtins=builtins,
            dispatch=dispatch,
            sight=sight,
            record_tainted_memory=memory_config.on_tainted == "record",
            bounds=reply_bounds,
            deep=None if swap is None else DeepTier(swap, deep_builtins, scheduler),
        )
        await serve(
            rpc_config,
            engines.for_stream,
            stores.sessions,
            RpcPorts(
                schedules=schedules,
                memory_cascade=memory_cascade,
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
