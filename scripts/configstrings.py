"""Find the text a person reads in a YAML file: names, descriptions and what a run step prints."""

import re

from shellstrings import shell_strings

PROSE_KEYS = frozenset({"name", "description"})
SHELL_KEY = "run"
_ENTRY = re.compile(r"(?P<lead> *(?:- +)?)(?P<key>[\w-]+):(?: +(?P<value>.*))?")
_BLOCK = re.compile(r"[|>][-+1-9]*(?: +#.*)?")
_DOUBLE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_SINGLE = re.compile(r"'((?:[^']|'')*)'")
_COMMENT = re.compile(r"(?:^| +)#.*")


def _scalar(value: str) -> str:
    if double := _DOUBLE.match(value):
        return double[1]
    if single := _SINGLE.match(value):
        return single[1].replace("''", "'")
    return _COMMENT.sub("", value)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def yaml_strings(text: str) -> list[tuple[int, str]]:
    """Return each ``name`` and ``description`` value and each shell string a ``run`` value has.

    Each comes with its first line; a block scalar is the lines indented past its key.
    """
    lines = text.split("\n")
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        entry = _ENTRY.fullmatch(lines[index])
        index += 1
        if entry is None or entry["key"] not in PROSE_KEYS | {SHELL_KEY}:
            continue
        first, value = index, entry["value"] or ""
        if _BLOCK.fullmatch(value):
            start, column = index, len(entry["lead"])
            while index < len(lines) and (
                not lines[index].strip() or _indent(lines[index]) > column
            ):
                index += 1
            first, value = start + 1, "\n".join(lines[start:index])
        elif entry["key"] in PROSE_KEYS:
            value = _scalar(value)
        if entry["key"] == SHELL_KEY:
            strings = shell_strings(value, just=False)
            found.extend((first + line - 1, string) for line, string in strings)
        else:
            found.append((first, value))
    return found
