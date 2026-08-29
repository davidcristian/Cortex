"""Composition root: build the runtime dependencies at the edge, then serve.

The one place that reads config and picks adapters (DI at the edge, AGENTS.md).
The per-capability builders live in `builders.py` (and `subagent_builders.py` for
delegation, `memory_builders.py` for recall), one per port, each returning the dependency
plus its closer, and `bounds.py` holds the boot checks no one config class can make itself;
this module reads the env configs, gates them, calls the builders, hands `StreamEngines` the
ports a turn runs over, and releases everything on the way out:

- PreferenceStore -> `RedisPreferenceStore` over the same CORTEX_REDIS_URL, holding the user's
  settings record so a choice survives a restart of either side.
- SessionStore  -> `RedisSessionStore` over CORTEX_REDIS_URL, holding the state that
  survives restarts and model swaps (the one hard rule).
- Clock -> `SystemClock`, shared by the turn engine, memory recaller, and tool/subagent audit.
- InferenceBackend / Memory / Tools / Subagents / History window / Output guardrail
  -> the builders (ADR-0007/0008/0009/0010/0012/0014/0015); every capability needing an
  external service is off by default so CI and the no-GPU dev loop run free of them
  (the pure guardrail, like the window, ships on).

What runs once per **Converse stream** rather than once per process is not a composition step
and does not live here: `engines.py` holds it, an object taking these names once and answering
the `EngineFactory` `serve` asks for.

Everything below the edge receives ports, never settings objects or env access.
"""

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
    SeamServerConfig,
)
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_reply import ReplyBoundsConfig
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.engines import DeepTier, StreamEngines
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
    subagents_config = check_tool_call_deadline(SubagentsConfig(), tools_config)
    schedule_config = ScheduleConfig()
    swap_config = SwapConfig()
    reply_bounds = ReplyBoundsConfig().bounds()
    clock = SystemClock()
    # The settings record rides the same Redis the conversation state does: durable for the same
    # reason (append-only + a named volume), so a choice outlives a body reinstall.
    stores = RedisStores.open(runtime.redis_url, store_factory, preference_factory)
    # The handoff's process-wide half (ADR-0030), or None when CORTEX_ESCALATION is off, which
    # is the default: nothing below changes shape for a deployment that never escalates. When it
    # is on, the inference backend must lease through the very manager the residency scope swaps
    # under, so it is built first and handed in.
    # One placer for the process: the subagent pool places against it, and the residency scope
    # tells it which model holds the card while a handoff runs, so the two must be one object
    # (ADR-0030 handoff-window addendum).
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb,
        cortex_reservation_gb=runtime.cortex_reservation_gb,
    )
    # The runtime passes one gate on its way out: the pairing neither container can check for
    # itself, a control call bounded here against the stop it waits on being bounded in the
    # sidecar's own env. Checked before anything else is built, so a mispaired deployment is
    # refused with almost nothing to release, and before boot recovery, whose own stops are
    # issued under exactly this deadline.
    swap = await check_control_deadline(
        build_swap_runtime(swap_config, runtime, inference, clock, AsyncioSleeper(), placer=placer)
    )
    backend, close_backend = await build_inference_backend(
        inference, runtime.cortex_model, manager=None if swap is None else swap.manager
    )
    memory, memory_cascade, close_memory = await build_memory(
        memory_config, clock, backend, runtime.cortex_model
    )
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
        placer=placer,
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
    # The handoff's other boot half, beside the deadline check and for the same reason: both are
    # swap wiring, so both live in `swap_builders.py` and the root only calls them.
    await recover_boot_residency(swap, clock)
    try:
        # The per-stream factory (`engines.py`), which is the one thing here that runs again
        # after boot: a Converse stream's own confirmer and progress sink are what it adds to
        # everything above, so it takes those names once instead of closing over them.
        engines = StreamEngines(
            sessions=stores.sessions,
            backend=backend,
            clock=clock,
            runtime=runtime,
            memory=memory,
            tools=tool_registry,
            builtins=builtins,
            policy=tools_config.dispatch_policy,
            sight=sight,
            # The core takes a bool; the composition root maps the string (ADR-0019).
            record_tainted_memory=memory_config.on_tainted == "record",
            bounds=reply_bounds,
            deep=None if swap is None else DeepTier(swap, deep_builtins, scheduler),
        )
        await serve(
            seam_config,
            engines.for_stream,
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
