"""Which module owns a logger name, read out of the brain's source rather than by importing it.

Split off `logcalls.py` when teaching that reader the second spelling a message is written in
brought it to the 300-line cap, along the seam its own docstring had drawn from the day it landed:
this module answers which module owns a logger name, and the module it stands on answers what one
call under that logger puts on its line. `samplecheck.py` asks this one which module a documented
sample's logger belongs to, and asks that one what the call there really writes.

**A logger name resolves to a file rather than to a package.** ``getLogger(__name__)`` is the
brain's usual spelling, and its answer is the module's own dotted path, which is exactly what a
sample prints between the level and the message. Two sinks name themselves instead, the recall
trail and the tool audit, because their lines are read as a trail rather than as one module's
account of itself. Every spelling is collected, so a sample naming any of them resolves, and a
logger name claimed by two files is a fault rather than a coin toss. A literal written inside the
call is read too, and is the one spelling no module here writes any more: it stays because such a
call is legal Python and a reader that stopped matching one would lose that logger in silence.

**A sink may bind its name above the call, and that is the third spelling.** A self-named logger
restated by documents is declared as a module constant so the constant registry can tie those
documents to it, which both of these sinks now are, and a reader that only knew a literal would
drop such a logger out of this answer the day it was named: the sample quoting it would then fail as
a logger no module declares, which is loud and points at the document rather than at the reader.
So a bare identifier is resolved against that module's own top level, by ``moduleconstants.py``,
which is the same reading `hostedtiers.py` makes of the sidecar's declarations. Nothing wider is
followed. A name imported from another module is refused rather than chased, an importer of the
brain being exactly what this tree may not become.

**A module may not spell one logger name twice.** A declaration is what the constant registry ties
the documents restating a name to, and a literal beside one holds two names where there was one:
move the literal alone and those documents go on being tied to a name the brain no longer writes,
every gate green. So a literal is refused when this module's own top level binds it. Nothing is
asked about how a declaration is spelled, so the rule needs no convention to run over, and a literal
in a module that binds nothing is left alone, being the legal Python the spelling above is read for.
The rule one word over, on the message such a call carries, is the same sentence and lives beside
the reading it is about, in `logcalls.py`.
"""

import re
from pathlib import Path

from logcalls import LogCallError, modules, parsed, read
from moduleconstants import constants

# How a module claims a logger, in the three spellings the brain uses. `__name__` resolves to the
# module's own dotted path; a literal is the name itself; and a bare identifier is a name the same
# module bound above the call, which is how a sink whose logger is restated by documents declares
# it for the constant registry to tie them to.
GET_LOGGER = re.compile(
    r"getLogger\(\s*(?:__name__|\"(?P<named>[^\"]+)\"|(?P<bound>[A-Za-z_]\w*))\s*\)"
)

# The module name that is a package rather than a module: `cortex_core/__init__.py` is the logger
# `cortex_core` and not `cortex_core.__init__`.
PACKAGE_MODULE = "__init__"


def dotted(relative: Path) -> str:
    """The dotted name `__name__` holds for a module at ``relative`` inside its source root."""
    parts = relative.with_suffix("").parts
    if parts[-1] == PACKAGE_MODULE:
        parts = parts[:-1]
    return ".".join(parts)


def _literal(named: str, text: str, shown: str) -> str:
    """The name a literal call claims, refused when the same module also binds it.

    Only the binding is what the constant registry ties documents to, so a module holding both
    spellings can move the literal alone and leave them restating a name nothing writes through.
    """
    strings, _ = constants(parsed(text, shown))
    declared = sorted(name for name, value in strings.items() if value == named)
    if declared:
        msg = (
            f"{shown} writes the logger {named!r} inside the call and binds it above as "
            f"{', '.join(declared)}; pass the binding, so the name is written once"
        )
        raise LogCallError(msg)
    return named


def claimed(claim: re.Match[str], text: str, inside: Path, shown: str) -> str:
    """The logger name one ``getLogger`` call claims, in whichever spelling it claims it.

    A bare identifier is resolved against the module's own top level and nothing wider: a name
    imported from elsewhere is refused rather than followed, since following one would make this
    reader an importer of the brain, which is the seam the architecture keeps shut.
    """
    named = claim["named"]
    if named is not None:
        return _literal(named, text, shown)
    bound = claim["bound"]
    if bound is None:
        return dotted(inside)
    strings, _ = constants(parsed(text, shown))
    resolved = strings.get(bound)
    if resolved is None:
        msg = f"{shown} names its logger {bound}, which its own top level binds to no string"
        raise LogCallError(msg)
    return resolved


def loggers(root: Path) -> dict[str, str]:
    """Every logger name the brain declares, against the repo-relative file that declares it."""
    found: dict[str, str] = {}
    for module, inside, shown in modules(root):
        text = read(module, shown)
        for claim in GET_LOGGER.finditer(text):
            name = claimed(claim, text, inside, shown)
            if name in found:
                msg = f"{shown} and {found[name]} both declare the logger {name!r}"
                raise LogCallError(msg)
            found[name] = shown
    return found
