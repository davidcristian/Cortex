"""Read every variable substitution a compose file spends, raising on every form it cannot name.

Split out of `defaultcheck.py`, which owns the rule, exactly as `composemounts.py` is split out
of `bindcheck.py`: this module owns only the reading. It is a character walk rather than a YAML
parse, because these gates are stdlib-only (`pyproject.toml` in this directory) and because a
substitution is not a YAML construct at all: compose interpolates the strings a YAML parse has
already produced, which is why one variable can be spelled as a whole value, inside a connection
string and inside a command argument, and why all three have to be read the same way.

**Seven forms, and the one that is not a substitution.** `$$` is compose's escape for a literal
dollar and is consumed whole, so `$${VAR}` is text and nothing is spent there. `${NAME}` and
`$NAME` name a variable with nothing to fall back on. `${NAME:-x}` and `${NAME-x}` carry a
default; `${NAME:+x}` and `${NAME+x}` carry a replacement; `${NAME:?x}` and `${NAME?x}` carry the
message an operator sees when the variable is missing. The operator is kept **as written** rather
than folded: `:-` and `-` disagree about a variable set to the empty string, so a reader that
called them one form would hand the rule two behaviours under one name.

Anything else raises rather than being skipped. A `$` that opens none of those forms, a brace that
never closes, a nested expansion, and a name that is not an identifier are each a fault, because a
reader that walked past the one spend a new override adds would leave the gate unable to fail.

**Nesting is the one of those four compose itself accepts, and it is still refused.**
`${A:-${B:-x}}` resolves to `B`'s value and then to `x`, measured on compose v2.39.1 (ADR-0029's
addendum on a non-chat artifact naming itself in the family, which wanted that shape as a rename's
compatibility shim and did not take it). It is refused here because every rule over these spends
compares a default as a value, and a default that is itself a variable has no value until a
deployment supplies one, so a reader that returned something for it would hand those rules a
comparison none of them can make. Raising is therefore the answer here, and teaching this reader
the form would first mean deciding what those rules should compare in that case.

**A whole-line comment is not read, and a trailing one is read like any other text.** Compose
interpolates neither, a comment not surviving the parse the interpolation runs over, so a default
written in one is prose either way, and prose that restates a value is `crosscheck.py`'s question,
which already registers two compose comments as far sides. Skipping the whole-line form is
therefore exact. Skipping the trailing form is not, and this reader deliberately does not try: a
`#` is a marker only outside a quoted scalar, so finding one means tracking quotes across a line,
and this tree's two folded block scalars already carry a line with an odd number of double quotes
and content compose does interpolate. A quoting model would have to track block scalars and their
indentation too, which is a YAML parser in a project with no dependencies, bought to allow a note
beside a value. The asymmetry is the whole argument: a note read as a spend is loud, the gate
naming one line twice, and one line from its remedy, which is to write the note above the value; a
`#` wrongly read as a marker would drop a real spend from the comparison in silence, which is the
failure this gate exists to remove.
"""

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
    """A compose file carries a `$` form this reader cannot read."""


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
