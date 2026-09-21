"""Wait for a model to become ready, or until the load timeout elapses."""

from datetime import timedelta

from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper


async def await_model_ready(
    host: ModelHost, model: str, *, clock: Clock, sleeper: Sleeper, plan: ResidencyPlan
) -> ModelHostState:
    """Poll ``status(model)`` until it settles or ``plan.load_timeout_s`` elapses.

    Returns ``READY`` or ``FAILED`` as soon as either is seen, and the last state seen on
    timeout, so the caller can tell a load still running from a start that never took.
    """
    # The deadline is read off the injected ``Clock`` rather than ``asyncio.timeout``, so a
    # test can drive the timeout path without a real wait.
    deadline = clock.now() + timedelta(seconds=plan.load_timeout_s)
    while True:
        state = await host.status(model)
        if state is ModelHostState.READY or state is ModelHostState.FAILED:
            return state
        if clock.now() >= deadline:
            return state
        await sleeper.sleep(plan.poll_interval_s)
