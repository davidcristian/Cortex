"""Read every variable substitution a compose file spends, refusing every form it cannot name."""

import re
from typing import NamedTuple

# The only comment marker YAML has, and the one shape of it this reader is sure about: a line
# whose first non-blank character is this one carries no value and expands nothing.
COMMENT_MARKER = "#"

# What compose may write between a variable's name and the closing brace, longest first so `:-`
# is never read as `:` followed by something else. A bare `${NAME}` carries none of them.
OPERATORS = (":-", ":?", ":+", "-", "?", "+")

# The operators whose argument is a VALUE the variable falls back to or is replaced by. The
# other two (`:?`, `?`) carry prose telling an operator what to set, and two spends wording that
# differently have not drifted, so only a value is ever compared.
VALUE_OPERATORS = frozenset({":-", "-", ":+", "+"})

_NAME = re.compile(r"[A-Za-z_]\w*")


class SubstitutionReadError(Exception):
    """A compose file carries a `$` form this reader will not guess at."""


class Substitution(NamedTuple):
    """One spend of one variable: where it is written, and what it falls back to."""

    line: int
    name: str
    operator: str
    argument: str

    @property
    def carries_value(self) -> bool:
        """Whether ``argument`` is a value the variable can take, rather than prose or nothing."""
        return self.operator in VALUE_OPERATORS

    @property
    def written(self) -> str:
        """The spend as a fault should show it, the bare form normalized to braces."""
        return f"${{{self.name}{self.operator}{self.argument}}}"


def _braced(number: int, text: str, start: int) -> tuple[Substitution, int]:
    """Read the `${...}` beginning at ``start``, and return the index just past it."""
    end = text.find("}", start)
    if end < 0:
        msg = f"line {number}: {text[start:]!r} opens a substitution that never closes"
        raise SubstitutionReadError(msg)
    body = text[start + 2 : end]
    if "{" in body:
        msg = f"line {number}: nested substitution ${{{body}}}, which compose does not expand"
        raise SubstitutionReadError(msg)
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
    """Return every substitution one line spends, in the order the line writes them."""
    found: list[Substitution] = []
    index = text.find("$")
    while index >= 0:
        if text.startswith("$$", index):
            index += 2  # compose's escape for a literal dollar, so nothing is spent here
        elif text.startswith("${", index):
            substitution, index = _braced(number, text, index)
            found.append(substitution)
        else:
            substitution, index = _bare(number, text, index)
            found.append(substitution)
        index = text.find("$", index)
    return found


def read_substitutions(text: str) -> list[Substitution]:
    """Return every substitution one compose file spends, skipping whole-line comments."""
    return [
        substitution
        for number, line in enumerate(text.splitlines(), start=1)
        if not line.lstrip().startswith(COMMENT_MARKER)
        for substitution in read_line(number, line)
    ]
