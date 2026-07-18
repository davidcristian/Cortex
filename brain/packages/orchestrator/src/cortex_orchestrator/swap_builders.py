"""Brain-handoff wiring: build the swap's runtime, or nothing at all (ADR-0030).

One builder per the composition root's usual contract, split from ``builders.py`` for the line
cap like the subagent and schedule ones. Everything here is off unless ``CORTEX_ESCALATION`` is
set, and "off" means genuinely absent: no model host, no swapping manager, no handoff store, no
conductor, and no ``escalate_to_brain`` in the built-in set. A deployment that never escalates
runs byte for byte the code it ran before this landed.

The two objects that must be shared rather than rebuilt per stream are built here: the model
host (it owns process residency) and the ``SwappingModelManager`` (it owns the one GPU lease, so
a second instance would be a second lease). The per-stream halves (the deep model's phase over
this stream's dispatcher, and the conductor that drives it) are assembled by the engine factory,
because they carry the stream's own confirmer and progress sink.
"""

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
    SwappingModelManager,
)
from cortex_model_manager import HttpModelHost
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import BrainRuntimeConfig, InferenceConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_session import RedisHandoffStore


@dataclass(frozen=True, slots=True)
class SwapRuntime:
    """The process-wide half of the handoff capability, built once per deployment.

    ``manager`` is both the GPU lease (the ``ModelManager`` the inference backend leases
    through) and the residency scope the conductor drives, which is exactly why it must be the
    same object in both roles: a swap that did not hold the lease would preempt a live round.
    """

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
    """Everything a handoff needs at process scope, or None when escalation is off.

    The endpoint map is composition-root config by design (ADR-0030 decision 5): the core is
    handed logical id to URL and never discovers either. With the echo inference backend the
    cortex endpoint is empty, which is harmless because nothing leases it, and the swap still
    exercises every path over the scripted host.

    Which host it is comes from ``CORTEX_MODELHOST_BACKEND``, and the config validator is what
    guarantees a backend was named, so there is no silent no-host path here.
    """
    if not swap.escalation:
        return None
    plan = swap.residency_plan(runtime.cortex_model)
    host, close_host = _build_model_host(swap, plan)
    endpoints = {plan.cortex_model: inference.endpoint, plan.brain_model: swap.brain_endpoint}
    handoffs = handoff_store_factory(runtime.redis_url)
    return SwapRuntime(
        host=host,
        manager=SwappingModelManager(host, endpoints, plan, clock, sleeper),
        handoffs=handoffs,
        plan=plan,
        close=_release_both(handoffs.aclose, close_host),
    )


def _build_model_host(
    swap: SwapConfig, plan: ResidencyPlan
) -> tuple[ModelHost, Callable[[], Awaitable[None]]]:
    """The configured model host, with the coroutine that releases whatever it holds.

    ``supervisor`` is the real adapter over the ``model-host`` sidecar's control API: it starts
    and stops actual ``llama-server`` processes, and its residency is therefore whatever that
    container is really running (nothing is asserted here, which is why boot recovery converges
    residency before the seam serves). ``scripted`` is the in-core twin, which tracks residency
    honestly and starts nothing, so it is told the standing resident is up.
    """
    if swap.modelhost_backend == "supervisor":
        client = build_control_client(swap.modelhost_timeout_s)
        return HttpModelHost(swap.modelhost_endpoint, client), client.aclose
    return ScriptedModelHost(running=[plan.cortex_model]), noop_aclose


def build_control_client(timeout_s: float) -> httpx.AsyncClient:
    """The control plane's HTTP client: one bounded deadline for every phase of a call.

    Deliberately unlike the generation clients (``builders.py``, ``read=None``): a control call
    that hung would hang a swap step under no bound at all. The bound has to clear the sidecar's
    own worst-case stop, which is why its default is a whole minute
    (``config_swap.DEFAULT_MODELHOST_TIMEOUT_S``).
    """
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
