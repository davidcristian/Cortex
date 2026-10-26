"""How long ago a recalled memory was written, in the words the rank and the reply show."""

from datetime import datetime, timedelta

_UNITS = (
    (timedelta(days=1), "day"),
    (timedelta(hours=1), "hour"),
    (timedelta(minutes=1), "minute"),
)


def written_ago(at: datetime, now: datetime) -> str:
    """The age of a memory written at ``at``, in its largest whole unit: ``3 days ago``."""
    elapsed = now - at
    # A date after now was written under a clock that ran ahead, so it says nothing about order.
    if elapsed < timedelta(0):
        return "age unknown"
    for unit, name in _UNITS:
        count = elapsed // unit
        if count >= 1:
            return f"{count} {name}{'' if count == 1 else 's'} ago"
    return "just now"


def aged(text: str, at: datetime, now: datetime) -> str:
    """The memory's text after its age in brackets, as both lists show it."""
    return f"({written_ago(at, now)}) {text}"
