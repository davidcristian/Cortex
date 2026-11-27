"""Read whether a forget call ran on a statement that asks to forget nothing when read alone."""

from cortex_core.forget_unrequested import asks_question, forget_unrequested
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.tools import ToolResult


def opened_earlier(query: str) -> bool:
    """Whether ``query`` asks no question and alone has the forget tool refused.

    Only an earlier exchange opened such a forget. A question such as ``What about my PIN 4821?``
    can ask to forget the value it names."""
    return FORGET_CHOSEN_TOOL_NAME in forget_unrequested(query) and not asks_question(query)


def keeps_unmatched(result: ToolResult, query: str) -> bool:
    """Whether a forget ``result`` that matched nothing leaves the turn asking ``query`` stored."""
    return result.matched_nothing and opened_earlier(query)
