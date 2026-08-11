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

The roster is the same widening taken one step further: which ids a host carries at all is
deployment env rather than a condition anything can arrange mid test, so ``HostUnderTest`` names
one id outside it and each fixture arranges that its own way.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest

from cortex_core import (
    ControlBounds,
    DeviceMemory,
    ModelHost,
    ModelHostError,
    ModelHostState,
    ModelNotHostedError,
)

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
    crash, a CUDA failure, or a child that could not bind its port. ``card(reading)`` is the third
    world-condition, added with the fit check: what the GPU this host supervises reports, or
    ``None`` for a host that can see none. ``aclose`` releases whatever the fixture built (the real
    adapter holds an HTTP client).

    ``bounds`` is not a world-condition but a wiring fact: the timing each fixture built its host
    with, which the host then has to report back. It is a field rather than a knob because these
    three are env in the real deployment, fixed for the life of a container, so a setter would
    model something that cannot happen. ``boot_id`` is the same kind of fact for the same reason:
    a process cannot change which boot it is, only be replaced by another process, which is a new
    fixture rather than a setter on this one.

    ``unhosted`` is a wiring fact of the third kind: an id this host does not carry. It is not a
    knob either, and for a reason worth stating, because it is the reason the whole distinction
    exists: a roster is the deployment's env, read once when the daemon comes up, so nothing a
    caller does can add an id to it or take one away. The supervisor fixture supplies one by
    leaving it out of the roster it builds; the twin is told, since a twin that starts no process
    would otherwise serve any name it was handed.
    """

    host: ModelHost
    serving: Callable[..., None]
    die: Callable[[str], None]
    card: Callable[[DeviceMemory | None], None]
    aclose: Callable[[], Awaitable[None]]
    bounds: ControlBounds
    boot_id: str
    unhosted: str


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


async def check_an_id_this_host_does_not_carry_is_refused_by_every_verb(
    subject: HostUnderTest,
) -> None:
    """An id outside the roster fails as ``ModelNotHostedError``, from all three lifecycle verbs.

    All three, because the caller that acts on the difference meets whichever comes first: boot
    recovery asks ``status`` before it asks ``stop``, and the swap back asks ``start``. An
    implementation that refused narrowly on one verb and broadly on another would make the
    distinction depend on where in a sequence the misconfiguration was met.

    The id is in the message on purpose. A deployment names several tiers and this failure is
    read by whoever has to correct one of them, so a refusal that did not say which id it was
    about would send an operator to the roster with nothing to look for.
    """
    for verb in (subject.host.status, subject.host.start, subject.host.stop):
        with pytest.raises(ModelNotHostedError) as excinfo:
            await verb(subject.unhosted)
        assert subject.unhosted in str(excinfo.value)


async def check_an_unhosted_refusal_is_still_a_model_host_error(subject: HostUnderTest) -> None:
    """The narrower failure is caught by every caller that only ever knew the broad one.

    Not a tautology about subclassing but the compatibility promise the port makes: ``swap_in``,
    ``restore_standing``, ``restart_evicted`` and the tier retry all catch ``ModelHostError`` and
    must go on catching this, so adding the distinction cannot turn a handled failure into an
    unhandled crash in a caller that never asked for it.
    """
    with pytest.raises(ModelHostError):
        await subject.host.status(subject.unhosted)


async def check_a_host_with_no_card_reports_no_device_memory(subject: HostUnderTest) -> None:
    """``None`` is an answer the port defines, not a failure: most deployments have no GPU.

    The swap is what decides that an absent reading refuses a handoff, and it can only decide
    that if every implementation says "none" the same way instead of raising.
    """
    subject.card(None)
    assert await subject.host.device_memory() is None


async def check_a_host_with_a_card_reports_what_is_free_and_how_big_it_is(
    subject: HostUnderTest,
) -> None:
    """The reading the fit check compares against, carried whole rather than as one number.

    Both figures, because the refusal an operator reads has to say how much of the card was free
    out of how much there is; a free figure alone cannot tell a small card from a busy one.
    """
    subject.card(DeviceMemory(free_mib=20033, total_mib=24463))
    assert await subject.host.device_memory() == DeviceMemory(free_mib=20033, total_mib=24463)


async def check_a_host_reports_the_control_bounds_it_was_wired_with(
    subject: HostUnderTest,
) -> None:
    """All three terms of the pairing rule, off the host that was given them.

    The composition root refuses to serve when their sum reaches the deadline it bounds a control
    call with, so an implementation that reported the shipped defaults, or dropped the probe term
    the other two cannot imply, would let a mispaired deployment through the one check there is.
    """
    assert await subject.host.control_bounds() == subject.bounds


async def check_a_host_names_which_boot_of_it_is_answering(subject: HostUnderTest) -> None:
    """The same daemon names itself the same way twice, and it names the one under test.

    The brain compares this value for equality and nothing else, so the only two properties that
    matter are that it is stable while a process lives (or every handoff would reconcile) and that
    it belongs to the host answering rather than to the fixture's expectation of it. An
    implementation minting one per request would pass any assertion made about a single read.
    """
    assert await subject.host.boot_id() == subject.boot_id
    assert await subject.host.boot_id() == subject.boot_id


ALL_CHECKS: tuple[Callable[[HostUnderTest], Awaitable[None]], ...] = (
    check_a_model_nobody_started_reports_stopped,
    check_start_begins_a_load_and_is_idempotent,
    check_stop_ends_the_model_and_is_idempotent,
    check_a_process_that_died_unasked_reports_failed,
    check_a_failed_model_is_restarted_without_being_stopped_first,
    check_stopping_a_model_that_already_died_settles_it,
    check_a_swap_leaves_only_the_model_it_swapped_in,
    check_an_id_this_host_does_not_carry_is_refused_by_every_verb,
    check_an_unhosted_refusal_is_still_a_model_host_error,
    check_a_host_with_no_card_reports_no_device_memory,
    check_a_host_with_a_card_reports_what_is_free_and_how_big_it_is,
    check_a_host_reports_the_control_bounds_it_was_wired_with,
    check_a_host_names_which_boot_of_it_is_answering,
)
