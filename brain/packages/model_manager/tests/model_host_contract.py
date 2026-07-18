"""Shared ``ModelHost`` behaviour checks. Every implementation must pass all of them.

This is the ports-before-adapters gate for the process-lifecycle port (AGENTS.md: the real adapter
must pass the same contract test as the fake). It is driven twice by
``test_model_host_contract.py``: over the core's ``ScriptedModelHost``, and over the real
``HttpModelHost`` talking to a real ``ModelSupervisor`` through a real Starlette app, with only the
OS spawn and the health socket faked. Every assertion is on what ``status`` answered after the
implementation under test did its own work, and the two legs are held to different depths on
purpose. On the **supervisor** leg the answer is derived rather than echoed (the exit code read
before the probe, the slot kept or replaced, the port a spec names), which is why the mutations
recorded in ``test_model_host_contract.py`` redden supervisor cases and no scripted ones. On the
**scripted** leg a state word the fixture handed the twin comes back verbatim, so what those
assertions pin is that the twin honours the world-condition it was given: that is what a fake owes
the contract, and it is the reason the real adapter is driven through the same script.

The port's own vocabulary needs two conditions of the world that no verb can create, so each
implementation supplies them as knobs on ``HostUnderTest``: whether a started model's server
answers readiness yet, and a process dying without being asked to. ``ScriptedModelHost`` scripts
them; the supervisor's fixture flips a fake probe and exits a fake child. That is the honest
widening of the contract, because "``start`` only begins loading" is not observable at all in an
implementation where nothing can be mid-load.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cortex_core import ModelHost, ModelHostState

# Two ids, so the swap-shaped check can watch one go down as the other comes up. Both fixtures
# declare exactly these.
CORTEX = "cortex"
DEEP = "deep-model"
CONTRACT_MODELS = (CORTEX, DEEP)


@dataclass(frozen=True, slots=True)
class HostUnderTest:
    """One ``ModelHost`` implementation plus the two world-conditions the checks arrange.

    ``serving(model, serving=...)`` decides whether that model's server answers readiness;
    ``die(model)`` makes its process disappear without anybody asking, which is the analogue of a
    crash, a CUDA failure, or a child that could not bind its port. ``aclose`` releases whatever
    the fixture built (the real adapter holds an HTTP client).
    """

    host: ModelHost
    serving: Callable[..., None]
    die: Callable[[str], None]
    aclose: Callable[[], Awaitable[None]]


async def check_a_model_nobody_started_reports_stopped(subject: HostUnderTest) -> None:
    """The starting point every swap assumes: an id with no process is STOPPED, not unknown."""
    assert await subject.host.status(DEEP) is ModelHostState.STOPPED


async def check_start_begins_a_load_and_is_idempotent(subject: HostUnderTest) -> None:
    """``start`` returns before the model serves, and starting twice still leaves one resident.

    The health gate is the only thing that decides readiness (``await_model_ready`` polls
    ``status``), so an implementation whose ``start`` reported ready would make the gate
    decorative. Both properties are load bearing: ``residency_moves`` re-issues ``start`` without
    checking first.
    """
    subject.serving(DEEP, serving=False)
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.LOADING
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.LOADING
    subject.serving(DEEP, serving=True)
    assert await subject.host.status(DEEP) is ModelHostState.READY


async def check_stop_ends_the_model_and_is_idempotent(subject: HostUnderTest) -> None:
    """A stopped model reports STOPPED even while its port would still answer.

    Deliberately leaves the readiness knob saying "serving": an implementation that decided state
    from a health probe alone would report the model it just stopped as READY, which is exactly
    how a real swap gets fooled by an incumbent process still holding the port.
    """
    subject.serving(CORTEX, serving=True)
    await subject.host.start(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.READY
    await subject.host.stop(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.STOPPED
    await subject.host.stop(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.STOPPED


async def check_a_process_that_died_unasked_reports_failed(subject: HostUnderTest) -> None:
    """A model nobody stopped, that is gone anyway, is FAILED: not STOPPED, and never READY.

    The distinction is what lets the health gate give up at once instead of waiting out the load
    bound, and what stops a swap from believing a dead start took. The readiness knob stays
    "serving" here for the same reason as above.
    """
    subject.serving(DEEP, serving=True)
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.READY
    subject.die(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.FAILED


async def check_a_failed_model_is_restarted_without_being_stopped_first(
    subject: HostUnderTest,
) -> None:
    """A crash is not terminal for the id, and no caller has to stop it before starting it again.

    This is the shape the swap back and boot recovery actually use: ``restore_standing`` stops the
    deep model and then starts the cortex, never stopping the cortex first, so a cortex that died
    while the deep model was resident is started over its own corpse. An implementation that
    remembered the old exit would report FAILED forever and every later turn would fail.
    """
    subject.serving(DEEP, serving=True)
    await subject.host.start(DEEP)
    subject.die(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.FAILED
    # The world lets it come up again (whatever killed it is gone). The implementation still owes
    # the recovery: replacing the dead process rather than remembering its exit.
    subject.serving(DEEP, serving=True)
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.READY


async def check_stopping_a_model_that_already_died_settles_it(subject: HostUnderTest) -> None:
    """A stop settles a slot whose process is already gone, waiting for no signal nobody can send.

    What the swap back does to a deep model that crashed mid answer: it stops it anyway, and that
    must complete rather than block on a corpse.
    """
    subject.serving(DEEP, serving=True)
    await subject.host.start(DEEP)
    subject.die(DEEP)
    await subject.host.stop(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.STOPPED


async def check_a_swap_leaves_only_the_model_it_swapped_in(subject: HostUnderTest) -> None:
    """The sequence ``swap_in`` performs: the standing resident down, the deep model up."""
    subject.serving(CORTEX, serving=True)
    subject.serving(DEEP, serving=True)
    await subject.host.start(CORTEX)
    await subject.host.stop(CORTEX)
    await subject.host.start(DEEP)
    assert (await subject.host.status(CORTEX), await subject.host.status(DEEP)) == (
        ModelHostState.STOPPED,
        ModelHostState.READY,
    )


ALL_CHECKS: tuple[Callable[[HostUnderTest], Awaitable[None]], ...] = (
    check_a_model_nobody_started_reports_stopped,
    check_start_begins_a_load_and_is_idempotent,
    check_stop_ends_the_model_and_is_idempotent,
    check_a_process_that_died_unasked_reports_failed,
    check_a_failed_model_is_restarted_without_being_stopped_first,
    check_stopping_a_model_that_already_died_settles_it,
    check_a_swap_leaves_only_the_model_it_swapped_in,
)
