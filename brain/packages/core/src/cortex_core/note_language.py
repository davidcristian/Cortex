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
        "tomorrow with am are was they don set reminder alarm meeting"
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
# German writes its nouns and the polite "Sie" capitalized anywhere, so a capital is no name there.
_ALWAYS_CAPITALIZED = _words("sie uhr morgen")
_MARKS: Mapping[str, str] = {"es": "¿¡"}
_WORD = re.compile(r"[^\W\d_]+")
_ENDS_SENTENCE = ".!?¿¡\n"
# A word of three letters or fewer in capitals reads as an abbreviation: EST, MON, LOS.
_LONGEST_ABBREVIATION = 3


def _opens_sentence(message: str, start: int) -> bool:
    before = message[:start].rstrip(" \t\"'(")
    return not before or before[-1] in _ENDS_SENTENCE


def _capitals(message: str, found: list[re.Match[str]]) -> list[str]:
    """The long words of a message with no lowercase letter, when two are in one language's list."""
    if any(char.islower() for char in message):
        return []
    long = [m.group().lower() for m in found if len(m.group()) > _LONGEST_ABBREVIATION]
    if any(sum(word in vocabulary for word in long) > 1 for vocabulary in _WORDS.values()):
        return long
    return []


def _counted(message: str) -> list[str]:
    """The lowercase words of ``message`` less abbreviations and names inside a sentence."""
    # "EU" and "Las Vegas" name nothing about the language; a lone "Sie" or "Uhr" still counts.
    found = list(_WORD.finditer(message))
    capital = [
        len(m.group()) > 1 and m.group()[0].isupper() and not _opens_sentence(message, m.start())
        for m in found
    ]
    padded = [False, *capital, False]
    return [
        m.group().lower()
        for i, m in enumerate(found)
        if not (len(m.group()) > 1 and m.group().isupper())
        and not (
            capital[i]
            and (padded[i] or padded[i + 2])
            and m.group().lower() not in _ALWAYS_CAPITALIZED
        )
    ] + _capitals(message, found)


def message_language(message: str) -> str:
    """The one language the most words and marks of ``message`` belong to, else English."""
    words = _counted(message)
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
