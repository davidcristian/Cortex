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

import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
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
    TierHealer,
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
    """The process-wide half of the handoff capability, built once per deployment.

    ``manager`` is both the GPU lease (the ``ModelManager`` the inference backend leases
    through) and the residency scope the conductor drives, which is exactly why it must be the
    same object in both roles: a swap that did not hold the lease would preempt a live round.

    ``healer`` is the one background loop this capability owns: it reads what every evictable
    peer tier is doing and puts back the ones that are not serving, whether or not a start of them
    ever failed (ADR-0030 tier-outage and tier-sweep addenda). It is started by boot
    recovery and stopped by ``close``, rather than by two more lines at a composition root that
    was at its line cap when it landed, which is also why it owns its own task.
    """

    host: ModelHost
    manager: SwappingModelManager
    handoffs: HandoffStore
    plan: ResidencyPlan
    healer: TierHealer
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
    """Everything a handoff needs at process scope, or None when escalation is off.

    ``placer`` is the same object the subagent pool places against, handed here so the residency
    scope can tell it which model holds the card while a handoff runs (ADR-0030 handoff-window
    addendum). It has to be one instance in both roles, or the correction would be written to a
    second placer nothing reads.

    The endpoint map is composition-root config by design (ADR-0030 decision 5): the core is
    handed logical id to URL and never discovers either. With the echo inference backend the
    cortex endpoint is empty, which is harmless because nothing leases it, and the swap still
    exercises every path over the scripted host.

    Which host it is comes from ``CORTEX_MODELHOST_BACKEND``, and the config validator is what
    guarantees a backend was named, so there is no unreported no-host path here.
    """
    if not swap.escalation:
        return None
    plan = swap.residency_plan(runtime.cortex_model)
    host, close_host = _build_model_host(swap, plan)
    endpoints = {plan.cortex_model: inference.endpoint, plan.brain_model: swap.brain_endpoint}
    handoffs = handoff_store_factory(runtime.redis_url)
    manager = SwappingModelManager(host, endpoints, plan, clock, sleeper, placer)
    healer = TierHealer(manager.heal_residency, interval_s=swap.swap_tier_heal_s)
    return SwapRuntime(
        host=host,
        manager=manager,
        handoffs=handoffs,
        plan=plan,
        healer=healer,
        close=_release_all(healer.aclose, handoffs.aclose, close_host),
    )


def _build_model_host(
    swap: SwapConfig, plan: ResidencyPlan
) -> tuple[ModelHost, Callable[[], Awaitable[None]]]:
    """The configured model host, with the coroutine that releases whatever it holds.

    ``supervisor`` is the real adapter over the ``model-host`` sidecar's control API: it starts
    and stops actual ``llama-server`` processes, and its residency is therefore whatever that
    container is really running (nothing is asserted here, which is why boot recovery converges
    residency before the seam serves). ``scripted`` is the in-core twin, which tracks residency
    and starts nothing, so it is told the standing resident is up.
    """
    if swap.modelhost_backend == "supervisor":
        client = build_control_client(swap.modelhost_timeout_s)
        return HttpModelHost(swap.modelhost_endpoint, client), client.aclose
    return ScriptedModelHost(running=[plan.cortex_model]), noop_aclose


def build_control_client(timeout_s: float) -> httpx.AsyncClient:
    """The control plane's HTTP client: one bounded deadline for every phase of a call.

    Deliberately unlike the generation clients (``builders.py``), whose read bound is a per-chunk
    stall ceiling rather than a deadline on the exchange: a control call streams nothing, so it has
    no such gap, and every phase of it is bounded by one number. The bound has to clear the
    sidecar's own worst-case stop, which is why its default is a whole minute
    (``config_swap.DEFAULT_MODELHOST_TIMEOUT_S``).
    """
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))


async def check_control_deadline(swap: SwapRuntime | None) -> SwapRuntime | None:
    """Raise when the model host's worst stop can outlast the deadline the brain bounds it with.

    The pairing (``probe_timeout_s + stop_grace_s + reap_timeout_s`` under
    ``CORTEX_MODELHOST_TIMEOUT_S``) spans two containers' env, so it used to be documented in
    three places and enforced in none. It is checkable now because the host reports the three
    bounds it was really given, and this is where it is checked: at wiring time, once, on the
    object that will spend the deadline. The deadline is read off the runtime's own plan rather
    than passed beside it, so this and the swap's re-reading of the same rule after a sidecar
    restart cannot be comparing against two different numbers.

    There are three outcomes and only one of them raises. A host that answers bounds the deadline
    does not clear is a static misconfiguration whose failure is intermittent (a stop pays the
    whole grace only when the tier it evicts was busy), so it raises here rather than being
    discovered inside one user's handoff, exactly as an escalation without a model host does. A
    host that cannot be reached does not raise: boot recovery already argues that a brain must
    start beside a sidecar that is down, since the restart policy revives one whose own boot
    default is cortex-up, and an unreachable sidecar is a condition that heals itself while a
    mispaired deadline is not. A host that answers no bounds at all is the scripted twin, which
    stops no process and therefore has no stop to bound.

    The runtime is handed straight back, so the composition root gates on the way through rather
    than holding an unchecked one for a statement. The raising path releases what that runtime
    already holds first, because the root's own shutdown hook is not armed until it returns.
    """
    if swap is None:
        return swap
    deadline_s = swap.plan.control_deadline_s
    try:
        bounds = await swap.host.control_bounds()
    except ModelHostError as err:
        _logger.warning(
            "the model host could not be asked for its control bounds; the deadline pairing is "
            "unchecked",
            extra={"deadline_s": deadline_s, "error": str(err)},
        )
        return swap
    if bounds is None:
        _logger.info(
            "the model host reports no control bounds, so nothing bounds its stop to check against",
            extra={"deadline_s": deadline_s},
        )
        return swap
    if bounds.clears(deadline_s):
        _logger.info(
            "the control deadline clears the model host's worst stop",
            extra={"deadline_s": deadline_s, "worst_s": bounds.worst_case_stop_s},
        )
        return swap
    # The three readings above are attached to the record alone, because the process entry's
    # formatter appends whatever a record carries and a second copy in the message would print each
    # of them twice. This failure is the one place the numbers stay in the prose: the same string
    # is the exception's text, read where no formatter runs, and a caller told only that the
    # pairing failed would have to go back to the logs to learn by how much.
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
    """Fail a crash-stranded handoff, converge the GPU, and publish what it observed.

    Boot recovery (ADR-0030 decision 4): a handoff cannot outlive its process, so any record a
    crash left behind is failed and the GPU is converged back onto the cortex before the seam
    serves its first turn. What it observed is published onto the manager (decision 6), because a
    boot that could not settle the cortex must not leave the seam answering ready off the
    manager's optimistic seed while every turn fails. Nothing here raises: a boot that cannot
    reach the model host still serves, and the report is what says so.

    Convergence writes the peers it could not start into the manager's own record rather than
    into its answer, so a boot whose delegation tier is broken publishes a serving report that
    names that tier instead of the amber one that says the usual assistant never came up. The
    record is reached through the manager because that is the object that owns it; the alternative
    was two records for one fact.

    The tier retry loop starts here too, at the one moment residency is as settled as this
    process can make it, and deliberately after the publish: a pass that ran first would be
    retrying against a residency record the boot seed had not replaced yet. A boot that marked a
    tier is exactly the case that loop has work to do on, from its very first pass.
    """
    if swap is None:
        return
    converged = await recover_handoffs(
        swap.handoffs,
        swap.host,
        swap.plan,
        swap.manager.standing_tiers,
        clock=clock,
        sleeper=AsyncioSleeper(),
    )
    await swap.manager.publish_boot_residency(serving=converged)
    swap.healer.start()


def swap_closer(swap: SwapRuntime | None) -> Callable[[], Awaitable[None]]:
    """The uniform shutdown hook: release what the runtime holds, or nothing when absent."""
    return noop_aclose if swap is None else swap.close


def _release_all(*releases: Callable[[], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    """Run every release in the order given, each one even if an earlier one failed.

    The order is the reverse of what the runtime acquired: the retry loop is stopped before the
    store and the client it spends are closed, or a pass in flight would find a closed client.
    The stack gives exactly the semantics the nested ``try``/``finally`` this replaces had for
    two, so a release that raises still leaves the rest to run and does not become a shutdown
    that stopped halfway.
    """

    async def close() -> None:
        async with AsyncExitStack() as stack:
            for release in reversed(releases):
                stack.push_async_callback(release)

    return close
