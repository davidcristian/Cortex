"""Read every variable substitution in a compose file, raising on every form it cannot read."""

import re
from typing import NamedTuple

COMMENT_MARKER = "#"

# Longest first, so `:-` is never read as `:` followed by something else.
OPERATORS = (":-", ":?", ":+", "-", "?", "+")

VALUE_OPERATORS = frozenset({":-", "-", ":+", "+"})

_NAME = re.compile(r"[A-Za-z_]\w*")


class SubstitutionReadError(Exception):
    """A compose file has a `$` form this reader cannot read."""


class Substitution(NamedTuple):
    """One use of one variable: where it is written, and what it falls back to."""

    line: int
    name: str
    operator: str
    argument: str

    @property
    def has_value(self) -> bool:
        """Whether ``argument`` is a value the variable can take, rather than prose or nothing."""
        return self.operator in VALUE_OPERATORS

    @property
    def written(self) -> str:
        """The substitution as a fault shows it, the bare form normalized to braces."""
        return f"${{{self.name}{self.operator}{self.argument}}}"


def _spend_extent(text: str, start: int, first_close: int) -> str:
    """The `${...}` at ``start`` as compose delimits it, for a fault to quote whole."""
    depth = 0
    for index in range(start + 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start : first_close + 1]


def _brace_fault(number: int, spend: str) -> str:
    """The fault for a substitution whose body has a `{`, naming what the brace opens."""
    if "${" in spend[2:]:
        return (
            f"line {number}: nested substitution {spend}, whose default is a second spend "
            "rather than a value, meaning one thing with nothing set and another once the "
            "inner variable is set"
        )
    return f"line {number}: {spend} has a brace in its argument, which this reader was not taught"


def _braced(number: int, text: str, start: int) -> tuple[Substitution, int]:
    """Read the `${...}` beginning at ``start``, and return the index just past it."""
    end = text.find("}", start)
    if end < 0:
        msg = f"line {number}: {text[start:]!r} opens a substitution that never closes"
        raise SubstitutionReadError(msg)
    body = text[start + 2 : end]
    if "{" in body:
        raise SubstitutionReadError(_brace_fault(number, _spend_extent(text, start, end)))
    name = _NAME.match(body)
    if name is None:
        msg = f"line {number}: ${{{body}}} names no variable"
        raise SubstitutionReadError(msg)
    rest = body[name.end() :]
    for operator in OPERATORS:
        if rest.startswith(operator):
            argument = rest[len(operator) :]
            return Substitution(number, name.group(), operator, argument), end + 1
    if rest:
        msg = f"line {number}: ${{{body}}} uses an operator this reader was not taught"
        raise SubstitutionReadError(msg)
    return Substitution(number, name.group(), "", ""), end + 1


def _bare(number: int, text: str, start: int) -> tuple[Substitution, int]:
    """Read the `$NAME` beginning at ``start``, and return the index just past it."""
    name = _NAME.match(text, start + 1)
    if name is None:
        msg = f"line {number}: {text[start : start + 2]!r} is a dollar that opens no substitution"
        raise SubstitutionReadError(msg)
    return Substitution(number, name.group(), "", ""), name.end()


def read_line(number: int, text: str) -> list[Substitution]:
    """Return every substitution on one line, in the order the line writes them."""
    found: list[Substitution] = []
    index = text.find("$")
    while index >= 0:
        if text.startswith("$$", index):
            index += 2
        elif text.startswith("${", index):
            substitution, index = _braced(number, text, index)
            found.append(substitution)
        else:
            substitution, index = _bare(number, text, index)
            found.append(substitution)
        index = text.find("$", index)
    return found


def read_substitutions(text: str) -> list[Substitution]:
    """Return every substitution in one compose file, skipping whole-line comments."""
    return [
        substitution
        for number, line in enumerate(text.splitlines(), start=1)
        if not line.lstrip().startswith(COMMENT_MARKER)
        for substitution in read_line(number, line)
    ]
