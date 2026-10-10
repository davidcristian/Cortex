"""The ``ServingProbe`` contract the fake and every adapter pass."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from cortex_core import ServingProbe


class ProbeUnderTest(Protocol):
    """Builds a probe whose part answers, or does not."""

    def __call__(self, *, answering: bool) -> ServingProbe: ...


type Check = Callable[[ProbeUnderTest], Awaitable[None]]


async def check_an_answering_part_has_no_fault(make: ProbeUnderTest) -> None:
    assert await make(answering=True).fault() is None


async def check_a_silent_part_has_a_one_line_fault(make: ProbeUnderTest) -> None:
    fault = await make(answering=False).fault()
    assert fault
    assert "\n" not in fault


async def check_a_fault_is_the_same_when_asked_again(make: ProbeUnderTest) -> None:
    probe = make(answering=False)
    assert await probe.fault() == await probe.fault()


async def check_the_part_has_a_one_line_name(make: ProbeUnderTest) -> None:
    for answering in (True, False):
        part = make(answering=answering).part
        assert part
        assert "\n" not in part


ALL_CHECKS: tuple[Check, ...] = (
    check_an_answering_part_has_no_fault,
    check_a_silent_part_has_a_one_line_fault,
    check_a_fault_is_the_same_when_asked_again,
    check_the_part_has_a_one_line_name,
)
