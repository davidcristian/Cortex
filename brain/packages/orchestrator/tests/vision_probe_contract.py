"""The `VisionProbe` contract, run over every implementation (AGENTS.md: ports before adapters).

The port's promises are short and every one of them is a safety property, so they are asserted
against the core's `ScriptedVisionProbe` and against the real `PropsVisionProbe` talking HTTP,
by the same checks (`test_vision_probe_contract.py`), on the `ModelHost` contract's model.

One condition no method on the port can create is the server changing between two calls, so each
fixture supplies it as a knob. That condition is why the port exists, since a model server can be
replaced under a brain that is not, and an implementation answering from a remembered result would
pass every other check.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import VisionProbe


@dataclass(frozen=True, slots=True)
class ProbeUnderTest:
    """One implementation plus the two ways a test may change the world it reads.

    `set_vision` makes the next call's correct answer True or False; `break_world` makes it
    unanswerable (a dead server, a body that will not parse). A fake has no way to fail on its
    own, so it satisfies `break_world` by scripting the answer the port owes for an unknown. The
    check states what an implementation must answer, and leaves open how it came to be unable to
    tell.
    """

    probe: VisionProbe
    set_vision: Callable[[bool], None]
    break_world: Callable[[], None]


type Check = Callable[[ProbeUnderTest], Awaitable[None]]


async def answers_what_the_world_reports(under_test: ProbeUnderTest) -> None:
    """The probe returns True for a server that reports a projector and False for one that does
    not."""
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True
    under_test.set_vision(False)
    assert await under_test.probe.can_see() is False


async def re_reads_the_world_on_every_call(under_test: ProbeUnderTest) -> None:
    """Every call reads the server again, so an earlier answer is never reused.

    A capture is authorized by the answer taken at the call, so an implementation that cached the
    first result would keep advertising and running the screen tool against a server that has
    been replaced under it.
    """
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True
    under_test.set_vision(False)
    assert await under_test.probe.can_see() is False
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True


async def an_unanswerable_world_is_no_vision(under_test: ProbeUnderTest) -> None:
    """A server the probe cannot read answers False, and the probe never raises at its caller.

    The caller is a tool registry mid-turn, so an exception escaping the probe would turn an
    unanswered check into a failed turn instead of a turn that runs with one fewer tool.
    """
    under_test.break_world()
    assert await under_test.probe.can_see() is False


ALL_CHECKS: Sequence[Check] = (
    answers_what_the_world_reports,
    re_reads_the_world_on_every_call,
    an_unanswerable_world_is_no_vision,
)
