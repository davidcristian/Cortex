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

    The model's text is the reply less the brain's notes; ``false_claim`` is set when one of those
    notes says no forget call in that turn deleted."""

    ask: str
    reply: str
    forgot: bool = False
    false_claim: bool = False


def names_forgetting(text: str) -> bool:
    """Whether ``text`` names forgetting or removing something."""
    return _ABOUT_FORGETTING.search(text) is not None or _NAMES_FORGETTING.search(text) is not None


def _names(exchange: Exchange) -> bool:
    return not exchange.false_claim and names_forgetting(exchange.reply)


def forget_open(exchanges: Sequence[Exchange]) -> bool:
    """Whether an exchange ran a forget call, has a reply naming forgetting, or asked to forget.

    A reply the brain closed with a note saying no forget call deleted names nothing."""
    return any(
        exchange.forgot or _names(exchange) or asks_to_forget(exchange.ask)
        for exchange in exchanges
    )
