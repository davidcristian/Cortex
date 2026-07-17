"""Brain-handoff wiring: build the swap's runtime, or nothing at all (ADR-0030)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cortex_core import (
    Clock,
    HandoffStore,
    ModelHost,
    ResidencyPlan,
    ScriptedModelHost,
    Sleeper,
    SwappingModelManager,
)
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import BrainRuntimeConfig, InferenceConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_session import RedisHandoffStore


@dataclass(frozen=True, slots=True)
class SwapRuntime:
    """The process-wide half of the handoff capability, built once per deployment."""

    host: ModelHost
    manager: SwappingModelManager
    handoffs: HandoffStore
    plan: ResidencyPlan
    close: Callable[[], Awaitable[None]]


def build_swap_runtime(
    swap: SwapConfig,
    runtime: BrainRuntimeConfig,
    inference: InferenceConfig,
    clock: Clock,
    sleeper: Sleeper,
    handoff_store_factory: Callable[[str], RedisHandoffStore] = RedisHandoffStore.from_url,
) -> SwapRuntime | None:
    """Everything a handoff needs at process scope, or None when escalation is off."""
    if not swap.escalation:
        return None
    plan = swap.residency_plan(runtime.cortex_model)
    host = ScriptedModelHost(running=[plan.cortex_model])
    endpoints = {plan.cortex_model: inference.endpoint, plan.brain_model: swap.brain_endpoint}
    handoffs = handoff_store_factory(runtime.redis_url)
    return SwapRuntime(
        host=host,
        manager=SwappingModelManager(host, endpoints, plan, clock, sleeper),
        handoffs=handoffs,
        plan=plan,
        close=handoffs.aclose,
    )


def swap_closer(swap: SwapRuntime | None) -> Callable[[], Awaitable[None]]:
    """The uniform shutdown hook: release the handoff store, or nothing when it was never built."""
    return noop_aclose if swap is None else swap.close
