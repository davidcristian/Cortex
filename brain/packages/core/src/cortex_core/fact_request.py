"""Read whether a request to remember or store opens the message and states one fact."""

import re

from cortex_core.fact_statement import POSSESSED_VALUE, STATED_OTHER, STATEMENT
from cortex_core.memory_request import REMEMBER_OTHER, SECOND_CLAUSE, SENTENCE_END, THANKS

# An English imperative to store, then the fact: "Store this: my phone is 0721 555 019."
_STORE = re.compile(
    r"\W*(?:please\s+)?(?:(?:save|store|keep|record|memori[sz]e)(?:\s+(?:this|that|it))?"
    r"|(?:write|note|jot)(?:\s+(?:this|that|it))?\s+down)\s*[:,]?\s+(?:that\s+)?",
    re.IGNORECASE,
)
_STORED = re.compile(rf"(?:{STATEMENT}|{POSSESSED_VALUE})\s*", re.IGNORECASE)
# A remember verb alone before a comma, as in "Recuerda, mi código es 4242."
_BARE = re.compile(r"\W*(?:recuerd[ae]|ret(?:enez|iens)|re[țţt]ine)(?=\s*,)", re.IGNORECASE)
_FACT_AFTER = re.compile(r"^[\s,:]*(?:(?:que|dass|c[ăa])\b|qu['\u2019])?\s*", re.IGNORECASE)
_STATED = re.compile(rf"{STATED_OTHER}\s*", re.IGNORECASE)
# An obligation of the assistant, a second `que tu` or a `să` asks for an action, not a fact.
_ASKS_OF_YOU = re.compile(
    r"\b(?:tu\s+(?:dois|devras|devrais)|vous\s+(?:devez|devrez|devriez)|il\s+faut|il\s+faudr\w+"
    r"|qu(?:e\s+|['\u2019])(?:tu|vous)|debes|deber[aá]s|deber[ií]as|deb[eé]is|tienes\s+que"
    r"|tendr[aá]s\s+que|ten[eé]is\s+que|hay\s+que|trebuie|s[ăã]|sollst|solltest|musst|mußt)\b",
    re.IGNORECASE,
)


def stores_fact(query: str) -> bool:
    """Whether ``query`` asks in English to store one fact it states with a value."""
    found = _STORE.match(query)
    one_sentence = SENTENCE_END.search(query.strip()) is None
    return found is not None and one_sentence and _STORED.fullmatch(query, found.end()) is not None


def asks_kept_fact_other(query: str) -> bool:
    """Whether ``query`` opens with a request to remember one fact stated with a copula.

    The request is in French, German, Spanish or Romanian, and only thanks may come before it."""
    offset = 0
    for sentence in SENTENCE_END.split(query):
        start = query.find(sentence, offset)
        offset = start + len(sentence)
        found = REMEMBER_OTHER.search(sentence) or _BARE.match(sentence)
        if found is None:
            continue
        rest = query[start + found.end() :]
        fact = THANKS.sub("", _FACT_AFTER.sub("", rest, count=1))
        before = THANKS.sub("", query[: start + found.start()])
        alone = SECOND_CLAUSE.search(fact) is None and _ASKS_OF_YOU.search(fact) is None
        stated = _STATED.fullmatch(fact) is not None
        return re.search(r"\w", before) is None and alone and stated
    return False
