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
