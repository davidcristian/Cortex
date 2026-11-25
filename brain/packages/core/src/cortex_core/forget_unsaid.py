"""Refuse a forget call naming a word that a request to remember in another language lacks."""

import re
from collections.abc import Sequence

from cortex_core.forget_open import Exchange, forget_open
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.memory_request import asks_kept_other, asks_to_forget
from cortex_core.tools import ToolCall

FORGET_UNSAID_MSG = (
    "REFUSED: the person asked you to remember something, and this call names words their "
    "message does not hold, so it was not run and the remembered exchanges are kept. Do not call "
    "it again in this turn, and answer the message itself."
)
_WORD = re.compile(r"\w+")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.casefold()))


def reads_call_words(query: str, earlier: Sequence[Exchange]) -> bool:
    """Whether ``query`` asks to remember in another language with no forget asked or opened."""
    return asks_kept_other(query) and not asks_to_forget(query) and not forget_open(earlier)


def forget_unsaid(call: ToolCall, query: str) -> bool:
    """Whether ``call`` forgets text holding a word that ``query`` lacks."""
    text = call.arguments.get("text")
    if call.name != FORGET_CHOSEN_TOOL_NAME or not isinstance(text, str):
        return False
    return not _words(text) <= _words(query)
