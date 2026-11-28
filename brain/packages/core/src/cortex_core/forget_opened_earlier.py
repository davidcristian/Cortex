"""Read whether a forget call ran on a statement that asks to forget nothing when read alone."""

from cortex_core.forget_unrequested import asks_question, forget_unrequested
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.tools import ToolResult, TurnStamp

UNKEPT_SINCE_NOTE = (
    "\n\n(Nothing in the user's message is kept in memory, because memory stores no turn that "
    "read this result, so do not say that anything in the message was noted, saved or "
    "remembered. If it asked you to remember anything, say that it was not kept and ask the user "
    "to send it again in a message of its own.)"
)


def opened_earlier(query: str) -> bool:
    """Whether ``query`` asks no question and alone has the forget tool refused.

    Only an earlier exchange opened such a forget. A question such as ``What about my PIN 4821?``
    can ask to forget the value it names."""
    return FORGET_CHOSEN_TOOL_NAME in forget_unrequested(query) and not asks_question(query)


def stored(stamp: TurnStamp) -> bool:
    """Whether memory stores the turn ``stamp`` names, as far as the results read so far show."""
    return not stamp.opaque and (stamp.record_tainted_memory or not stamp.tainted)


def keeps_unmatched(result: ToolResult, stamp: TurnStamp) -> bool:
    """Whether a forget ``result`` that matched nothing leaves the turn ``stamp`` names stored."""
    return result.matched_nothing and stored(stamp) and opened_earlier(stamp.query)


def unkept_since(before: TurnStamp, after: TurnStamp, unmatched: int) -> str:
    """The note a result ends with when it stops memory storing a turn ``keeps_unmatched`` kept.

    ``unmatched`` counts the turn's forget runs that matched nothing, each left without its note."""
    if unmatched and stored(before) and not stored(after) and opened_earlier(after.query):
        return UNKEPT_SINCE_NOTE
    return ""
