"""What the GPU is serving right now, in the words shown to a human."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResidencyReport:
    """One answer about the GPU: whether the usual assistant serves, why not, and notes on it."""

    serving: bool
    detail: str
    notes: tuple[str, ...] = ()


def with_note(report: ResidencyReport, note: str) -> ResidencyReport:
    """A serving report that also says ``note``; a report that is not serving is unchanged."""
    if not report.serving:
        return report
    return ResidencyReport(serving=True, detail=report.detail, notes=(*report.notes, note))


type ResidencyPublisher = Callable[[str | None, ResidencyReport], Awaitable[None]]


# Answered synchronously: read with nothing awaited between the answer and the call it
# guards, no handoff can begin in the gap, so a caller that must skip a pass rather than
# queue gets an answer it can act on.
type Fence = Callable[[], bool]


RESIDENCY_SERVING = ResidencyReport(serving=True, detail="")

RESIDENCY_LOADING = ResidencyReport(
    serving=False, detail="swapping to the deep model; this takes a few minutes"
)

RESIDENCY_DEEP = ResidencyReport(serving=False, detail="a deep task is in progress")

RESIDENCY_RESTORING = ResidencyReport(serving=False, detail="bringing the usual assistant back")

RESIDENCY_LOST = ResidencyReport(
    serving=False,
    detail="the usual assistant could not be reloaded after a deep task; recovery is manual",
)

RESIDENCY_BOOT_FAILED = ResidencyReport(
    serving=False,
    detail="the usual assistant did not come up at startup; the model host needs attention",
)
