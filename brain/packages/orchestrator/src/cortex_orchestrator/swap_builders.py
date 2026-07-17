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

    The host is the ``scripted`` one: it tracks which models are resident and reports readiness,
    so every branch of the swap runs, but it starts no process and moves no weights. The config
    validator is what guarantees a backend was named, so there is no silent no-host path here;
    the real supervisor adapter arrives as a second backend value and is what makes the swap
    move actual weights.
    """
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
