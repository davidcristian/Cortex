"""Pick the language a closing note is written in from the person's message."""

import re
from collections.abc import Mapping

ENGLISH = "en"


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Only words one of the five languages uses alone count: "la", "de", "que" do not. Letters only
# break a tie, because a name such as Jürgen or María has them in a message of any language.
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
# A word one list counts and another language writes too: a lone "ce" is French or Romanian.
_ALSO_WRITTEN: Mapping[str, frozenset[str]] = {"fr": _words("ce")}
# German writes its nouns and the polite "Sie" capitalized anywhere, so a capital is no name there.
_ALWAYS_CAPITALIZED = _words("sie uhr morgen")
_MARKS: Mapping[str, str] = {"es": "¿¡"}
_LETTERS: Mapping[str, str] = {
    "fr": "éèêëàâçîïôûùœ",
    "de": "äöüß",
    "es": "ñáéíóú",
    "ro": "ăâîșşțţ",
}
_WORD = re.compile(r"[^\W\d_]+")
_ENDS_SENTENCE = ".!?¿¡\n"
# A word of three letters or fewer in capitals reads as an abbreviation: EST, MON, LOS.
_LONGEST_ABBREVIATION = 3
# German closes „ with the “ English opens with. A single quote closes a quote only at a word's
# edge, and a straight one opens one only there, so "don't" stays a word with either apostrophe.
_QUOTED = re.compile(
    r"«[^«»\n]+»|»[^«»\n]+«|„[^„“”\n]+[“”]|\"[^\"\n]+\"|“[^“”\n]+”"
    r"|(?<!\w)'(?:[^'\n]|(?<=\w)'(?=\w))+'(?!\w)"
    r"|\u2018(?:[^\u2018\u2019\n]|(?<=\w)\u2019(?=\w))+\u2019(?!\w)"
)


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


def _letters(message: str, language: str) -> int:
    """How many letters of ``message`` are among those ``language`` writes and English does not."""
    return sum(message.lower().count(letter) for letter in _LETTERS.get(language, ""))


def _score(message: str, words: list[str], language: str) -> int:
    return sum(word in _WORDS[language] for word in words) + sum(
        message.count(mark) for mark in _MARKS.get(language, "")
    )


def _leaders(message: str) -> list[str]:
    """The languages the most words and marks of ``message`` belong to; none when nothing does."""
    words = _counted(message)
    scores = {language: _score(message, words, language) for language in _WORDS}
    best = max(scores.values())
    return [language for language, score in scores.items() if score == best] if best > 0 else []


def forget_language(message: str) -> str:
    """The one language the forget readers read ``message`` in, else English; letters not read."""
    leaders = _leaders(message)
    return leaders[0] if len(leaders) == 1 else ENGLISH


def _most_letters(message: str, languages: list[str]) -> list[str]:
    letters = {language: _letters(message, language) for language in languages}
    most = max(letters.values(), default=0)
    return [language for language in languages if letters[language] == most]


def _also_writing(message: str, leader: str) -> list[str]:
    """The other languages that write the one word ``leader`` scores in ``message``, if any."""
    words = _counted(message)
    found = [word for word in words if word in _WORDS[leader]]
    if _score(message, words, leader) != 1 or not found:
        return []
    return [language for language, also in _ALSO_WRITTEN.items() if found[0] in also]


def _pick(message: str) -> str:
    """The one language the most words and marks of ``message`` belong to, then the one whose
    letters it holds most, else English. A lone word another language also writes goes to
    whichever of the two has more of its letters."""
    leaders = _most_letters(message, _leaders(message))
    if len(leaders) != 1:
        return ENGLISH
    rivals = _most_letters(message, [leaders[0], *_also_writing(message, leaders[0])])
    return rivals[0] if len(rivals) == 1 else leaders[0]


def message_language(message: str) -> str:
    """The language a closing note on ``message`` is written in, picked from its words outside
    quotes, or from the whole message when those score nothing."""
    unquoted = _QUOTED.sub(" ", message)
    return _pick(unquoted if _leaders(unquoted) else message)


def in_language(english: str, others: Mapping[str, str], language: str) -> str:
    """``english`` written in ``language`` when ``others`` has it, else ``english``."""
    return others.get(language, english)
