"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md).
The per-capability builders live in `builders.py` (and `subagent_builders.py` for
delegation, `memory_builders.py` for recall), one per port, each returning the dependency
plus its closer; this module only reads the env configs, calls them, hands the `TurnEngine`
its ports, and releases everything on the way out:

- PreferenceStore -> `RedisPreferenceStore` over the same CORTEX_REDIS_URL, holding the user's
  settings record so a choice survives a restart of either side.
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
from dataclasses import replace

from cortex_core import (
    AsyncioSleeper,
    BrainPhase,
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
from cortex_orchestrator.stores import RedisStores
from cortex_orchestrator.subagent_builders import build_subagent_tools, build_subagents
from cortex_orchestrator.swap_builders import build_swap_runtime, swap_closer
from cortex_orchestrator.vision import build_vision
from cortex_session import RedisPreferenceStore, RedisSessionStore


async def run_from_env(
    *,
    store_factory: Callable[[str], RedisSessionStore] = RedisSessionStore.from_url,
    preference_factory: Callable[[str], RedisPreferenceStore] = RedisPreferenceStore.from_url,
) -> None:
    """Compose the brain from the environment and serve until shutdown.

    `store_factory` and `preference_factory` exist so tests can substitute fakeredis-backed
    stores; the production entrypoint always uses the defaults. The store's connections and every
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
    swap_config = SwapConfig()
    clock = SystemClock()
    # The settings record rides the same Redis the conversation state does: durable for the same
    # reason (append-only + a named volume), so a choice outlives a body reinstall.
    stores = RedisStores.open(runtime.redis_url, store_factory, preference_factory)
    # The handoff's process-wide half (ADR-0030), or None when CORTEX_ESCALATION is off, which
    # is the default: nothing below changes shape for a deployment that never escalates. When it
    # is on, the inference backend must lease through the very manager the residency scope swaps
    # under, so it is built first and handed in.
    swap = build_swap_runtime(swap_config, runtime, inference, clock, AsyncioSleeper())
    backend, close_backend = build_inference_backend(
        inference, runtime.cortex_model, manager=None if swap is None else swap.manager
    )
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
    # The built-in set is confirmer-independent, so it is assembled once (ADR-0025 d7);
    # the ticker fires beside `serve` and is stopped before its store closes.
    # Vision is discovered, not declared (ADR-0029): the running llama-server reports its own
    # modalities, so a brain-side boolean can never disagree with it. The bounds say the tool may
    # be registered at all (a body can take a picture); the probe is what the tool's registry asks
    # on every advertisement and every call, because the server answering can be replaced under a
    # brain that never restarts, and a stale yes spends the whole privacy cost of a screen read on
    # an image nothing can read (ADR-0029 live-probe addendum). Both are absent without a body.
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
    # The deep tier's own set, and the only difference is vision (ADR-0029 decision 6: no
    # brain-tier candidate on the mount carries a projector, so that tier is text-only by
    # construction). The probe above asked the CORTEX endpoint, and after a swap the model
    # serving is a different one at a different URL, so registration has to follow the tier that
    # will actually answer. Offering it there spends the whole privacy cost of a screen read
    # (pixels blitted, host receipt fired, turn tainted and opaque) on a picture nothing can
    # read, which is the exact trade the probe exists to prevent.
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
    if swap is not None:
        # Boot recovery (ADR-0030 decision 4): a handoff cannot outlive its process, so any
        # record a crash left behind is failed and the GPU is converged back onto the cortex
        # before the seam serves its first turn. What it observed is published onto the manager
        # (decision 6), because a boot that could not settle the cortex must not leave the seam
        # answering ready off the manager's optimistic seed while every turn fails.
        converged = await recover_handoffs(
            swap.handoffs, swap.host, swap.plan, clock=clock, sleeper=AsyncioSleeper()
        )
        await swap.manager.publish_boot_residency(serving=converged)
    try:

        def capabilities(confirmer: Confirmer, progress: ProgressSink) -> TurnCapabilities:
            # One capability bundle per Converse stream (ADR-0022/0010): the stream's confirmer
            # reaches the dispatcher and its progress sink reaches the turn (so a spawned
            # subagent surfaces onto this stream's overlay), everything else being the same
            # shared adapters.
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
            # The escalating wrapper (ADR-0030 decision 5): a fresh slot and inner engine per
            # turn, and a conductor over THIS stream's dispatcher, so the deep model's phase
            # runs the same audited tools the cortex phase did, minus the screen (ADR-0029). The
            # deep phase carries no slot either: it cannot escalate to itself.
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
                BrainPhase(stores.sessions, backend, clock, swap.plan.brain_model, deep),
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
