"""Read a reply in French, German, Spanish or Romanian that says something was noted or kept."""

import re
from collections.abc import Sequence

from cortex_core.forget_languages import FUNCTION
from cortex_core.forget_unnamed import row_words

_KEPT_FR = r"(?:not[ée]|enregistr[ée]|m[ée]moris[ée]|retenu|pris\s+note)\w*"
_PRONOUN_FR = r"(?:le\s+|la\s+|les\s+|l['\u2019])?"
_SOME_DE = r"(?:(?!(?:nicht|nie|kein\w*)\b)[\w'\u2019]+\s+){0,4}?"
_CLAIM = re.compile(
    rf"\bc['\u2019]est\s+(?:bien\s+|aussi\s+)?{_KEPT_FR}"
    rf"|\bj['\u2019]ai\s+(?:bien\s+|aussi\s+|d[ée]j[àa]\s+)?{_KEPT_FR}"
    rf"|\bje\s+(?:l['\u2019]|les\s+)ai\s+(?:bien\s+)?{_KEPT_FR}"
    rf"|(?<!\bque\s)\bje\s+{_PRONOUN_FR}(?:retiens|retiendrai|note|noterai|m[ée]moriserai"
    r"|enregistrerai)\b"
    rf"|\bje\s+(?:m['\u2019]en\s+souviendrai|vais\s+(?:m['\u2019]en\s+souvenir"
    rf"|{_PRONOUN_FR}(?:noter|retenir|m[ée]moriser|enregistrer)))\b"
    r"|\b(?:ist|sind|wurde)\s+(?:jetzt\s+|schon\s+|nun\s+)?(?:notiert|gespeichert|vermerkt|gemerkt)\b"
    rf"|\bich\s+(?:habe\s+{_SOME_DE}(?:notiert|gespeichert|vermerkt|gemerkt|aufgeschrieben)"
    rf"|werde\s+{_SOME_DE}(?:merken|notieren|speichern|aufschreiben)"
    r"|merke?\s+(?:es\s+|das\s+)?mir(?![^,.;:!?]*\b(?:schlecht|gut|schwer|leicht)\b)"
    r"|notiere|speichere)\b"
    r"|\b(?:merke?|notiere|speichere)\s+ich\b"
    r"|(?<!\bque\s)\b(?:lo|la|los|las)\s+(?:he\s+)?(?:anotad|apuntad|guardad|memorizad|registrad)"
    r"[oa]s?\b|\b(?:recordar[ée]|guardar[ée]|anotar[ée]|apunto|anoto|tendr[ée]\s+en\s+cuenta"
    r"|tengo\s+en\s+cuenta|tomo\s+nota)\b"
    r"|\b(?:he|queda)\s+(?:anotado|apuntado|guardado|memorizado|registrado|tomado\s+nota)\b"
    r"|\bam\s+(?:notat|re[țţt]inut|salvat|memorat|[îi]nregistrat)\b|\b(?:e|este)\s+notat\b"
    r"|\bvoi\s+(?:[țţt]ine\s+minte|re[țţt]ine|nota|salva|memora)\b"
    r"|\bo\s+s[ăa]\s+(?:[țţt]in\s+minte|re[țţt]in|notez|salvez)\b|\bre[țţt]in\b",
    re.IGNORECASE,
)
_OPENING = re.compile(
    r"^\W*(?:(?:d['\u2019]accord|ok|okay|parfait|alles\s+klar|gut|vale|perfecto|entendido|bine"
    r"|perfect)\W+)?(?:notée?s?|notiert|vermerkt|gespeichert|anotado|apuntado|guardado|notat"
    r"|re[țţt]inut|salvat)\b",
    re.IGNORECASE,
)
_CONDITION = re.compile(
    r"(?<!\w)(?:si|s['\u2019]ils?|quand|wenn|falls|sofern|sobald|cuando|dac[ăa]|c[âa]nd)(?!\w)",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"(?<!\w)n['\u2019-](?=\w)"
    r"|(?<!\w)(?:pas|jamais|rien|nicht|nie|niemals|kein\w*|no|nunca|nada|nu|nimic|niciodat[ăa])"
    r"(?!\w)",
    re.IGNORECASE,
)
_CLAUSE_END = re.compile(r"[,;:]|\b(?:et|mais|und|aber|y|pero|și|şi|dar)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# Only verbs of keeping or saving, since a fact "noted" in a reply is a new one.
_KEEPING = re.compile(r"guard|salv|speicher|enregistr", re.IGNORECASE)
_FUNCTION = frozenset(word for words in FUNCTION.values() for word in words)
_NUMBER = re.compile(r"\d+(?:[ .\-/]\d+)*")


def claims_kept_other(reply: str) -> bool:
    """Whether a statement in ``reply`` says in one of four other languages that it kept a fact."""
    if _OPENING.search(reply.lstrip().partition("\n")[0]):
        return True
    return any(
        stated(sentence, match)
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for match in _CLAIM.finditer(sentence)
    )


def _clause(sentence: str, match: re.Match[str]) -> tuple[int, int]:
    """Where the clause of ``sentence`` holding ``match`` starts and ends."""
    starts = [found.end() for found in _CLAUSE_END.finditer(sentence, 0, match.start())]
    after = _CLAUSE_END.search(sentence, match.end())
    return (starts[-1] if starts else 0), (len(sentence) if after is None else after.start())


def after_condition(sentence: str, end: int) -> bool:
    """Whether a condition word such as ``si``, ``wenn`` or ``dacă`` comes before ``end``."""
    return _CONDITION.search(sentence, 0, end) is not None


def stated(sentence: str, match: re.Match[str]) -> bool:
    """Whether ``match`` follows no condition in ``sentence`` and its clause holds no negation."""
    if after_condition(sentence, match.start()):
        return False
    start, end = _clause(sentence, match)
    return _NEGATION.search(sentence, start, end) is None


def names_spared_other(reply: str, spared: Sequence[str]) -> bool:
    """Whether each claim of ``reply`` in another language keeps only a row still stored."""
    held = {word for text in spared for word in row_words(text)}
    objects = [
        (match.group(), _object(sentence, match))
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for match in _CLAIM.finditer(sentence)
        if stated(sentence, match)
    ]
    opening = _OPENING.search(reply.lstrip().partition("\n")[0]) is not None
    return (
        bool(objects)
        and not opening
        and all(
            _KEEPING.search(verb) and keeps_held(row_words(text) - _FUNCTION, text, held, spared)
            for verb, text in objects
        )
    )


def _object(sentence: str, match: re.Match[str]) -> str:
    """The clause of ``sentence`` holding ``match``, without it."""
    start, end = _clause(sentence, match)
    return f"{sentence[start : match.start()]} {sentence[match.end() : end]}"


def _numbers(text: str) -> set[str]:
    """The digits of each number ``text`` names, its groups joined."""
    return {"".join(re.findall(r"\d", match.group())) for match in _NUMBER.finditer(text)}


def keeps_held(words: set[str], text: str, held: set[str], spared: Sequence[str]) -> bool:
    """Whether a keep claim's object ``text`` has ``words``, all in ``held``, and only numbers
    a row of ``spared`` holds."""
    numbers = {number for row in spared for number in _numbers(row)}
    return bool(words) and words <= held and _numbers(text) <= numbers
