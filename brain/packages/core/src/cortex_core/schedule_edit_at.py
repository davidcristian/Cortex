"""Read an ``edit_scheduled`` call that moves a one-time item to a new ``at``."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from cortex_core.schedule import ScheduledItem
from cortex_core.schedule_args import BAD_TEXT, parse_at
from cortex_core.schedule_day_args import has_day_selector
from cortex_core.schedule_time import DisplayZone

AT_ALONE = (
    "'at' moves a one-time item to a new date and time, so do not combine it with 'at_time', "
    "'every_seconds', 'starting', 'in_zone' or a day selector; give another zone's time as an "
    "offset in 'at'"
)
_RULE_ARGUMENTS = ("at_time", "every_seconds", "starting", "in_zone")
REPEAT_PROPERTY: dict[str, dict[str, Any]] = {
    "repeat": {
        "type": "boolean",
        "description": (
            "True only when the person asked for a one-time item to repeat; a one-time item "
            "takes 'at_time' only with it (optional)."
        ),
    }
}


def once_kept(item: ScheduledItem | None, arguments: Mapping[str, Any]) -> str | None:
    """The refusal of an ``at_time`` that would make a one-time ``item`` repeat, else ``None``."""
    if item is None or item.rule is not None or item.every is not None:
        return None
    if arguments.get("at_time") is None or arguments.get("repeat") is True:
        return None
    return (
        f"REFUSED: {item.id} is a one-time item, and 'at_time' would make it repeat, every day "
        "or on the days given, so this call was not run. To move it and keep it one time, call "
        "again with 'at' set to the ISO-8601 date-time of its new due time and no 'at_time' or "
        "day selector. Only if the person asked for it to repeat, call again with these "
        "arguments and 'repeat' set to true."
    )


def at_repeats(item_id: str) -> str:
    """The correction for an ``at`` on an item that repeats."""
    return (
        f"{item_id} repeats, so 'at' cannot move it; change its time with 'at_time', or move "
        "only its next occurrence with snooze_scheduled"
    )


def raced(item_id: str) -> str:
    """The correction for a move that a fire or a cancel raced."""
    return f"{item_id} changed underneath (fired or cancelled); use list_scheduled to re-check"


def parse_move(
    arguments: Mapping[str, Any], *, now: datetime, zone: DisplayZone
) -> tuple[str | None, datetime] | str:
    """The new text, if any, and the new due time of a call with ``at``, or a correction."""
    if has_day_selector(arguments) or any(
        arguments.get(key) is not None for key in _RULE_ARGUMENTS
    ):
        return AT_ALONE
    text = arguments.get("text")
    if text is not None and (not isinstance(text, str) or not text.strip()):
        return BAD_TEXT
    due = parse_at(arguments.get("at"), now, zone)
    if isinstance(due, str):
        return due
    return (text if isinstance(text, str) else None), due
