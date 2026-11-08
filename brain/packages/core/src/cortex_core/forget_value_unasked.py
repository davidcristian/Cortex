"""Refuse a forget of a value the person's message does not hold, after a delete left it held."""

from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.memory_values import digit_runs, whole_values
from cortex_core.tools import ToolCall

FORGET_VALUE_MSG = (
    "REFUSED: an earlier call in this turn already deleted what the person asked to forget, and "
    "the person's message does not hold this value, so this call was not run and the remembered "
    "exchanges holding the value are kept. Call it again only if the person's message asked to "
    "forget the value itself; otherwise tell the user what was forgotten."
)


def _keys(text: str) -> set[str]:
    """The values ``text`` holds, codes and years alike, by their letters and digits."""
    return {*whole_values(text), *digit_runs(text)}


def value_unasked(call: ToolCall, query: str, *, left: bool) -> bool:
    """Whether ``call`` forgets a value ``query`` lacks while rows hold a deleted number."""
    text = call.arguments.get("text")
    if call.name != FORGET_CHOSEN_TOOL_NAME or not left or not isinstance(text, str):
        return False
    named = _keys(text)
    return bool(named) and named.isdisjoint(_keys(query))
