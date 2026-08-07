"""Shared ``ModelHost`` behaviour checks. Every implementation must pass all of them."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cortex_core import DeviceMemory, ModelHost, ModelHostState

# Two ids, so the swap-shaped check can watch one go down as the other comes up. Both fixtures
# declare exactly these.
CORTEX = "cortex"
DEEP = "deep-model"
CONTRACT_MODELS = (CORTEX, DEEP)


@dataclass(frozen=True, slots=True)
class HostUnderTest:
    """One ``ModelHost`` implementation plus the two world-conditions the checks arrange."""

    host: ModelHost
    serving: Callable[..., None]
    die: Callable[[str], None]
    card: Callable[[DeviceMemory | None], None]
    aclose: Callable[[], Awaitable[None]]


async def check_a_model_nobody_started_reports_stopped(subject: HostUnderTest) -> None:
    """The starting point every swap assumes: an id with no process is STOPPED, not unknown."""
    assert await subject.host.status(DEEP) is ModelHostState.STOPPED


async def check_start_begins_a_load_and_is_idempotent(subject: HostUnderTest) -> None:
    """``start`` returns before the model serves, and starting twice still leaves one resident."""
    subject.serving(DEEP, serving=False)
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.LOADING
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.LOADING
    subject.serving(DEEP, serving=True)
    assert await subject.host.status(DEEP) is ModelHostState.READY


async def check_stop_ends_the_model_and_is_idempotent(subject: HostUnderTest) -> None:
    """A stopped model reports STOPPED even while its port would still answer."""
    subject.serving(CORTEX, serving=True)
    await subject.host.start(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.READY
    await subject.host.stop(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.STOPPED
    await subject.host.stop(CORTEX)
    assert await subject.host.status(CORTEX) is ModelHostState.STOPPED


async def check_a_process_that_died_unasked_reports_failed(subject: HostUnderTest) -> None:
    """A model nobody stopped, that is gone anyway, is FAILED: not STOPPED, and never READY."""
    subject.serving(DEEP, serving=True)
    await subject.host.start(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.READY
    subject.die(DEEP)
    assert await subject.host.status(DEEP) is ModelHostState.FAILED


async def check_a_failed_model_is_restarted_without_being_stopped_first(
    subject: HostUnderTest,
) -> None:
    """A crash is not terminal for the id, and no caller has to stop it before starting it again."""
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


ALL_CHECKS: tuple[Callable[[HostUnderTest], Awaitable[None]], ...] = (
    check_a_model_nobody_started_reports_stopped,
    check_start_begins_a_load_and_is_idempotent,
    check_stop_ends_the_model_and_is_idempotent,
    check_a_process_that_died_unasked_reports_failed,
    check_a_failed_model_is_restarted_without_being_stopped_first,
    check_stopping_a_model_that_already_died_settles_it,
    check_a_swap_leaves_only_the_model_it_swapped_in,
    check_a_host_with_no_card_reports_no_device_memory,
    check_a_host_with_a_card_reports_what_is_free_and_how_big_it_is,
)
