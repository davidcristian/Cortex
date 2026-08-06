"""The `VisionProbe` contract, run over every implementation (AGENTS.md: ports before adapters)."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import VisionProbe


@dataclass(frozen=True, slots=True)
class ProbeUnderTest:
    """One implementation plus the two ways a test may change the world it reads."""

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
    """The clause this port exists for: yesterday's answer is never reused."""
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True
    under_test.set_vision(False)
    assert await under_test.probe.can_see() is False
    under_test.set_vision(True)
    assert await under_test.probe.can_see() is True


async def an_unanswerable_world_is_no_vision(under_test: ProbeUnderTest) -> None:
    """Fail closed: not knowing is answered no, and never raised at the caller."""
    under_test.break_world()
    assert await under_test.probe.can_see() is False


ALL_CHECKS: Sequence[Check] = (
    answers_what_the_world_reports,
    re_reads_the_world_on_every_call,
    an_unanswerable_world_is_no_vision,
)
