"""Pick the language a closing note is written in from the person's message."""

import re
from collections.abc import Mapping

ENGLISH = "en"


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Only words one of the five languages uses alone count: "la", "de", "que" do not. Letters are
# not read, because a name such as Jürgen or María has them in a message of any language.
_WORDS: Mapping[str, frozenset[str]] = {
    ENGLISH: _words(
        "i my me the is to and please remind remember forget you it of at for what this that "
        "tomorrow with am are was"
    ),
    "fr": _words(
        "je j vous nous est et mais pour avec dans qui pas mon mes moi le les des au aux cette "
        "rappelle souviens oublie demain merci"
    ),
    "de": _words(
        "ich mich mir du dich dir sie ist und nicht das der die den dem ein eine mein meine bitte "
        "erinnere merke vergiss morgen um uhr für mit zu auf"
    ),
    "es": _words(
        "el los las del y es está mis recuérdame recuerda olvida mañana por para con una favor "
        "hola gracias guarda guardes"
    ),
    "ro": _words(
        "și şi este nu eu mea meu mele pentru cu că să pe din amintește aminteşte uită mâine "
        "rog mulțumesc ora care ce"
    ),
}
_MARKS: Mapping[str, str] = {"es": "¿¡"}
_WORD = re.compile(r"[^\W\d_]+")


def message_language(message: str) -> str:
    """The one language the most words and marks of ``message`` belong to, else English."""
    words = [word.lower() for word in _WORD.findall(message)]
    scores = {
        language: sum(word in vocabulary for word in words)
        + sum(message.count(mark) for mark in _MARKS.get(language, ""))
        for language, vocabulary in _WORDS.items()
    }
    best = max(scores.values())
    leaders = [language for language, score in scores.items() if score == best]
    return leaders[0] if best > 0 and len(leaders) == 1 else ENGLISH


def in_language(english: str, others: Mapping[str, str], language: str) -> str:
    """``english`` written in ``language`` when ``others`` has it, else ``english``."""
    return others.get(language, english)
