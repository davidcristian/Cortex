"""Read whether one of the last two exchanges of a chat opened a forget, from what each one did."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from cortex_core.memory_request import asks_to_forget

# Narrower than the forget refusal's retract words, since a reply often says "don't", "no" or
# "changes".
_ABOUT_FORGETTING = re.compile(
    r"\b(?:rid|unlearn\w*|no\s+longer|any\s?more|gone|take\s+back|out\s+of\s+(?:your|memory)|bin"
    r"|scrub\w*|ditch\w*|scrap\w*|toss\w*|trash\w*|expung\w+|shred\w*|unsav\w*|unremember\w*"
    r"|unstor\w*|let\s+go|retract\w*|revok\w+|withdraw\w*)\b",
    re.IGNORECASE,
)
_NAMES_FORGETTING = re.compile(
    r"\b(?:forg[eo]t|delet|eras|remov|wip(?:e|es|ed|ing)\b|clear|drop|discard|purg|vergiss|vergess"
    r"|vergeet|l[oö]sch|loesch|gel[oö]sch|geloesch|entfern|oubli|effac|olv[ií]d|b[oó]rr|ui[tțţ]|[șşs]ters"
    r"|[șşs]terg|sup{1,2}r[ií]m|elim[ií]n|ret[ií]r|enl[eè]v|qu[ií]t(?!e\b)\w|scoa[st]|scos|sco[țţt]i|streich"
    r"|gestrichen)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Exchange:
    """One earlier exchange as stored: the person's text, the model's text, whether a forget ran.

    The model's text is the reply less the notes the brain appended to it."""

    ask: str
    reply: str
    forgot: bool = False


def names_forgetting(text: str) -> bool:
    """Whether ``text`` names forgetting or removing something."""
    return _ABOUT_FORGETTING.search(text) is not None or _NAMES_FORGETTING.search(text) is not None


def forget_open(exchanges: Sequence[Exchange]) -> bool:
    """Whether an exchange ran a forget call, has a reply naming forgetting, or asked to forget."""
    return any(
        exchange.forgot or names_forgetting(exchange.reply) or asks_to_forget(exchange.ask)
        for exchange in exchanges
    )
