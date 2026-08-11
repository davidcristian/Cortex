"""The readiness gate every model start is bounded by (ADR-0030 decision 4 step 3).

``ModelHost.start`` only begins loading, so "the brain is up" is a fact only ``status`` can
report. This is the one place that waits for it: poll, settle, or give up on a clock-measured
bound. Pure policy over three ports (``ModelHost`` + ``Clock`` + ``Sleeper``), shared by the
residency scope's swap-in and swap-back and by boot recovery, so all three agree on what
"ready" means and on how long they will wait for it.

Deliberately no ``asyncio.timeout``: the bound is read off the injected ``Clock`` and the wait
between polls goes through the injected ``Sleeper``, so a test drives the whole gate, including
its timeout path, without a wall-clock sleep or a real deadline.
"""

from datetime import timedelta

from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper


async def await_model_ready(
    host: ModelHost, model: str, *, clock: Clock, sleeper: Sleeper, plan: ResidencyPlan
) -> ModelHostState:
    """Poll ``status(model)`` until it settles or ``plan.load_timeout_s`` elapses.

    Returns ``READY`` when the model is serving and ``FAILED`` when the host says it died, both
    as soon as they are observed; on the bound elapsing it returns the last state seen
    (``LOADING`` for a load that is still grinding, ``STOPPED`` for a start that never took), so
    the caller can say which of the two happened. A ``ModelHostError`` from ``status`` propagates
    on the first poll: the swap turns it into a failed swap rather than guessing. That covers a
    dead supervisor and, as ``ModelNotHostedError``, an id the host does not carry, and the two
    want the same thing here even though they mean opposite things to the caller, since a bound
    spent polling is a bound spent either way: a host that is not answering will not answer this
    call, and a roster that lacks an id will not grow one inside the load timeout.

    The deadline is computed once, before the first poll, so a zero bound is already expired and
    the first non-settled status ends the gate without any wait, which is how the swap suite
    exercises the timeout path deterministically.
    """
    deadline = clock.now() + timedelta(seconds=plan.load_timeout_s)
    while True:
        state = await host.status(model)
        if state is ModelHostState.READY or state is ModelHostState.FAILED:
            return state
        if clock.now() >= deadline:
            return state
        await sleeper.sleep(plan.poll_interval_s)
