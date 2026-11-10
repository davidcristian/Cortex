"""Read the whole values a text holds, such as a phone number or a code, as a person writes them."""

import re

_GROUP = r"\b(?=[^\W_]*\d)[^\W_]+"
_RUN = re.compile(rf"{_GROUP}(?:[ ./-]{_GROUP})*")
_SEPARATOR = re.compile(r"[ ./-]")
_DIGIT_RUN = re.compile(r"\d+(?:[ ./-]\d+)*")
_MIN_DIGITS = 4
_YEAR_DIGITS = 4
_DATE_PART_DIGITS = 2
_TIME = re.compile(r"\d{1,2}h\d{2}", re.IGNORECASE)
_UNIT_AFTER = re.compile(
    r"\s?(?:[%€$£]|(?:h|uhr|am|pm|eur|euros?|dollars?|usd|pounds?|gbp|chf|francs?|lei|ron)\b)",
    re.IGNORECASE,
)
_UNIT_BEFORE = re.compile(r"[€$£]\s?$")
_CODE_WORD = re.compile(
    r"\b(?:\w*codes?|pins?|numbers?|\w*nummer\w*|\w*zahl|num[ée]ros?|n[uú]meros?|c[oó]digos?"
    r"|claves?|cod(?:ul|ului|uri)?|num[aă]r(?:ul|ului)?|\w*passwor[dt]s?|\w*kennwort|contrase[nñ]as?"
    r"|parol[aă]|combinations?|combinaisons?|\w*kombination|mots?\s+de\s+passe|combos?"
    r"|combinaci[oó]n(?:es)?|combina[tțţ]i[ae])\b",
    re.IGNORECASE,
)

_ANY_KIND = re.compile(
    r"codes?|numbers?|nummer[ns]?|zahl|num[ée]ros?|n[uú]meros?|c[oó]digos?|cod(?:ul|ului|uri)?"
    r"|num[aă]r(?:ul|ului)?|combos?",
    re.IGNORECASE,
)
_COMPOUND = re.compile(
    r"([^\W\d_]{3,}?)(?:codes?|nummer\w*|zahl|passwor[dt]s?|kennwort|kombination)", re.IGNORECASE
)


def _is_year(group: str) -> bool:
    """Whether ``group`` reads as a year from 1900 to 2099."""
    return group.isdigit() and len(group) == _YEAR_DIGITS and group[:2] in {"19", "20"}


def _dated(groups: list[str]) -> bool:
    """Whether ``groups`` are a year alone or a date: a year among groups of at most two digits."""
    long_groups = sum(not group.isdigit() or len(group) > _DATE_PART_DIGITS for group in groups)
    return long_groups == 1 and any(_is_year(group) for group in groups)


def whole_values(text: str) -> dict[str, str]:
    """Each whole value of ``text`` by its letters and digits in lower case, mapped to its form."""
    values: dict[str, str] = {}
    for match in _RUN.finditer(text):
        groups = _SEPARATOR.split(match.group())
        key = "".join(groups).lower()
        if (
            sum(char.isdigit() for char in key) < _MIN_DIGITS
            or _dated(groups)
            or any(_TIME.fullmatch(group) for group in groups)
            or _UNIT_AFTER.match(text, match.end())
            or _UNIT_BEFORE.search(text[max(match.start() - 2, 0) : match.start()])
        ):
            continue
        values.setdefault(key, match.group())
    return values


def digit_runs(text: str) -> dict[str, str]:
    """Each run of four or more digits in ``text``, years and codes alike, by its digits alone."""
    runs: dict[str, str] = {}
    for match in _DIGIT_RUN.finditer(text):
        key = "".join(_SEPARATOR.split(match.group()))
        if len(key) >= _MIN_DIGITS:
            runs.setdefault(key, match.group())
    return runs


def code_word(word: str) -> bool:
    """Whether ``word`` names a kind of value, such as a code, a number or a password."""
    return _CODE_WORD.fullmatch(word) is not None


def kind_word(word: str) -> bool:
    """Whether the code word ``word`` names one kind of value, such as ``PIN``, not any code."""
    return code_word(word) and _ANY_KIND.fullmatch(word) is None


def code_stem(word: str) -> str | None:
    """The part of a compound code word such as ``doorcode`` before its code word, if any."""
    found = _COMPOUND.fullmatch(word)
    if found is None or code_word(found.group(1)):
        return None
    return found.group(1).lower()


def code_runs(text: str) -> dict[str, str]:
    """The digit runs of ``text``, a year or a date only when ``text`` names a code or a number."""
    named = _CODE_WORD.search(text) is not None
    runs = digit_runs(text).items()
    return {key: form for key, form in runs if named or not _dated(_SEPARATOR.split(form))}


def joined(text: str) -> str:
    """``text`` in lower case with every separator a value's groups can have removed."""
    return _SEPARATOR.sub("", text).lower()
