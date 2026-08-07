"""Brain-handoff wiring: build the swap's runtime, or nothing at all (ADR-0030)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from cortex_core import (
    Clock,
    HandoffStore,
    ModelHost,
    ResidencyPlan,
    ScriptedModelHost,
    Sleeper,
    SubagentPlacer,
    SwappingModelManager,
)
from cortex_model_manager import HttpModelHost
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


def build_swap_runtime(  # noqa: PLR0913 -- one more injected collaborator than the DI ceiling
    swap: SwapConfig,
    runtime: BrainRuntimeConfig,
    inference: InferenceConfig,
    clock: Clock,
    sleeper: Sleeper,
    handoff_store_factory: Callable[[str], RedisHandoffStore] = RedisHandoffStore.from_url,
    placer: SubagentPlacer | None = None,
) -> SwapRuntime | None:
    """Everything a handoff needs at process scope, or None when escalation is off."""
    if not swap.escalation:
        return None
    plan = swap.residency_plan(runtime.cortex_model)
    host, close_host = _build_model_host(swap, plan)
    endpoints = {plan.cortex_model: inference.endpoint, plan.brain_model: swap.brain_endpoint}
    handoffs = handoff_store_factory(runtime.redis_url)
    return SwapRuntime(
        host=host,
        manager=SwappingModelManager(host, endpoints, plan, clock, sleeper, placer),
        handoffs=handoffs,
        plan=plan,
        close=_release_both(handoffs.aclose, close_host),
    )


def _build_model_host(
    swap: SwapConfig, plan: ResidencyPlan
) -> tuple[ModelHost, Callable[[], Awaitable[None]]]:
    """The configured model host, with the coroutine that releases whatever it holds."""
    if swap.modelhost_backend == "supervisor":
        client = build_control_client(swap.modelhost_timeout_s)
        return HttpModelHost(swap.modelhost_endpoint, client), client.aclose
    return ScriptedModelHost(running=[plan.cortex_model]), noop_aclose


def build_control_client(timeout_s: float) -> httpx.AsyncClient:
    """The control plane's HTTP client: one bounded deadline for every phase of a call."""
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))


def swap_closer(swap: SwapRuntime | None) -> Callable[[], Awaitable[None]]:
    """The uniform shutdown hook: release what the runtime holds, or nothing when absent."""
    return noop_aclose if swap is None else swap.close


def _release_both(
    store: Callable[[], Awaitable[None]], host: Callable[[], Awaitable[None]]
) -> Callable[[], Awaitable[None]]:
    """Release the handoff store and the model host's client, the second even if the first fails."""

    async def close() -> None:
        try:
            await store()
        finally:
            await host()

    return close
