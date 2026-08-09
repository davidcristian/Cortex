"""Brain-handoff wiring: build the swap's runtime, or nothing at all (ADR-0030)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from cortex_core import (
    AsyncioSleeper,
    Clock,
    HandoffStore,
    ModelHost,
    ModelHostError,
    ResidencyPlan,
    ScriptedModelHost,
    Sleeper,
    SubagentPlacer,
    SwappingModelManager,
    recover_handoffs,
)
from cortex_model_manager import HttpModelHost
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import BrainRuntimeConfig, InferenceConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_session import RedisHandoffStore

_logger = logging.getLogger(__name__)


class ControlDeadlineError(RuntimeError):
    """The control deadline this brain was given does not clear its model host's worst stop."""


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


async def check_control_deadline(swap: SwapRuntime | None) -> SwapRuntime | None:
    """Refuse a deployment whose model host can outlast the deadline the brain bounds it with."""
    if swap is None:
        return swap
    deadline_s = swap.plan.control_deadline_s
    try:
        bounds = await swap.host.control_bounds()
    except ModelHostError as err:
        _logger.warning(
            "the model host could not be asked for its control bounds; the deadline pairing is "
            "unchecked: deadline_s=%s error=%s",
            deadline_s,
            err,
            extra={"deadline_s": deadline_s, "error": str(err)},
        )
        return swap
    if bounds is None:
        _logger.info(
            "the model host reports no control bounds, so nothing bounds its stop to check "
            "against: deadline_s=%s",
            deadline_s,
            extra={"deadline_s": deadline_s},
        )
        return swap
    if bounds.clears(deadline_s):
        _logger.info(
            "the control deadline clears the model host's worst stop: deadline_s=%s worst_s=%s",
            deadline_s,
            bounds.worst_case_stop_s,
            extra={"deadline_s": deadline_s, "worst_s": bounds.worst_case_stop_s},
        )
        return swap
    msg = (
        f"CORTEX_MODELHOST_TIMEOUT_S is {deadline_s} s and the model host's worst stop is "
        f"{bounds.worst_case_stop_s} s (probe {bounds.probe_timeout_s} s, grace "
        f"{bounds.stop_grace_s} s, reap {bounds.reap_timeout_s} s), so a control call would time "
        "out on an eviction that was still working and abort the handoff that asked for it. "
        "Raise the brain's deadline above that sum, or lower the sidecar's own bounds "
        "(docs/runbooks/model-swap.md)"
    )
    _logger.error(msg, extra={"deadline_s": deadline_s, "worst_s": bounds.worst_case_stop_s})
    await swap.close()
    raise ControlDeadlineError(msg)


async def recover_boot_residency(swap: SwapRuntime | None, clock: Clock) -> None:
    """Fail a crash-stranded handoff, converge the GPU, and publish what it observed."""
    if swap is None:
        return
    converged = await recover_handoffs(
        swap.handoffs, swap.host, swap.plan, clock=clock, sleeper=AsyncioSleeper()
    )
    await swap.manager.publish_boot_residency(serving=converged)


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
