"""Close a reply over a one-time reminder an edit made repeat on chosen days."""

from cortex_core.schedule_day_args import has_day_selector
from cortex_core.schedule_verbs import CANCEL_SCHEDULED_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME
from cortex_core.tools import ToolCall, ToolResult

MADE_REPEATING_NOTE = (
    "\n\n(This reminder now repeats. Ask to make it one time again if you meant only once.)"
)
MADE_REPEATING_NOTES = {
    "fr": "\n\n(Ce rappel se répète désormais. Demandez à le rendre de nouveau unique si vous ne "
    "le vouliez qu'une fois.)",
    "de": "\n\n(Diese Erinnerung wiederholt sich jetzt. Bitten Sie darum, sie wieder einmalig zu "
    "machen, wenn Sie sie nur einmal wollten.)",
    "es": "\n\n(Este recordatorio ahora se repite. Pide que vuelva a ser de una sola vez si lo "
    "querías solo una vez.)",
    "ro": "\n\n(Acest memento se repetă acum. Cere să fie din nou o singură dată dacă îl voiai "
    "doar o dată.)",
}


def made_repeating_after(
    call: ToolCall, result: ToolResult, held: tuple[str, ...]
) -> tuple[str, ...]:
    """The ids an edit made repeat on chosen days from one time: ``held``, plus one, less ends."""
    item = call.arguments.get("id")
    if result.is_error or not isinstance(item, str):
        return held
    arguments = call.arguments
    timed = arguments.get("at_time") is not None
    asked = arguments.get("repeat") is True and timed and has_day_selector(arguments)
    if call.name == EDIT_SCHEDULED_TOOL_NAME and asked and result.was_once:
        return held if item in held else (*held, item)
    # A daily rule has its own note, and an interval or a cancel ends the rule on chosen days.
    ended = call.name == CANCEL_SCHEDULED_TOOL_NAME or (
        call.name == EDIT_SCHEDULED_TOOL_NAME
        and (
            arguments.get("every_seconds") is not None
            or (timed and not has_day_selector(arguments))
        )
    )
    return tuple(each for each in held if not ended or each != item)
