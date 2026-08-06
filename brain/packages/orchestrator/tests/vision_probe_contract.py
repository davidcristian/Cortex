"""The `VisionProbe` contract, run over every implementation (AGENTS.md: ports before adapters).

The port's promises are short and every one of them is a safety property, so they are asserted
against the core's `ScriptedVisionProbe` and against the real `PropsVisionProbe` talking HTTP,
by the same checks (`test_vision_probe_contract.py`), on the `ModelHost` contract's model.

The port needs one condition of the world no method can create, so each fixture supplies it as a
knob: **the world changes between two questions**. That is the whole reason the port exists (a
model server is replaced under a brain that is not), and an implementation that answered from a
remembered verdict would pass every other check.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import VisionProbe


@dataclass(frozen=True, slots=True)
class ProbeUnderTest:
    """One implementation plus the two ways a test may change the world it reads.

    `set_vision` makes the next question's honest answer True or False; `break_world` makes it
    unanswerable (a dead server, a body that will not parse). A fake has no way to fail on its
    own, so it satisfies `break_world` by scripting the answer the port owes for an unknown, which
    is the honest widening: the check states what an implementation must *answer*, not how it
    came to be unable to tell.
    """

    probe: VisionProbe
    set_vision: Callable[[bool], None]
    break_world: Callable[[], None]


type Check = Callable[[ProbeUnderTest], Awaitable[None]]


async def answers_what_the_world_reports(under_test: ProbeUnderTest) -> None:
    """A server with a projector is believed, and so is one without."""
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True
    under_test.set_vision(False)
    assert await under_test.probe.can_see() is False


async def re_reads_the_world_on_every_call(under_test: ProbeUnderTest) -> None:
    """The clause this port exists for: yesterday's answer is never reused.

    A capture is authorized by the answer taken at the call, so an implementation that cached
    the first verdict would keep advertising and running the screen against a server that has
    been replaced under it.
    """
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True
    under_test.set_vision(False)
    assert await under_test.probe.can_see() is False
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True


async def an_unanswerable_world_is_no_vision(under_test: ProbeUnderTest) -> None:
    """Fail closed: not knowing is answered no, and never raised at the caller.

    Raising would be worse than useless here. The caller is a tool registry mid-turn, and an
    exception escaping it would turn "we could not check" into a failed turn instead of a turn
    that runs with one fewer tool.
    """
    under_test.break_world()
    assert await under_test.probe.can_see() is False


ALL_CHECKS: Sequence[Check] = (
    answers_what_the_world_reports,
    re_reads_the_world_on_every_call,
    an_unanswerable_world_is_no_vision,
)
