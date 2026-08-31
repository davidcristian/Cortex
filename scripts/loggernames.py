"""Which module owns a logger name, read out of the brain's source rather than by importing it.

`samplecheck.py` asks this module which file a documented sample's logger belongs to, and asks
`logcalls.py` what the call there writes. The ADR-0009 one-name addendum argues the rules below.

A logger name resolves to a file rather than to a package: `getLogger(__name__)` answers with the
module's dotted path, which is what a sample prints between the level and the message. Two sinks
name themselves instead, the recall trail and the tool audit, because their lines are read as a
trail rather than as one module's account of itself. A name claimed by two files raises.

`getLogger` is matched in three forms. `__name__` and a string literal are read directly. A bare
identifier is resolved against that module's own top level by `moduleconstants.py`, which is how a
self-named sink declares the name the constant registry ties documents to. Nothing wider is
followed: a name imported from another module raises, because resolving one would make this reader
an importer of the brain.

A module may not write one logger name twice. A literal beside a binding of the same string holds
two names where there was one, so moving the literal alone would leave the documents tied to a
name the brain no longer writes with every gate green. A literal is therefore refused when the
module's own top level binds it, and left alone otherwise. The matching rule for the message such
a call carries is in `logcalls.py`.
"""

import re
from pathlib import Path

from logcalls import LogCallError, modules, parsed, read
from moduleconstants import constants

# How a module claims a logger, in the three forms the brain writes. `__name__` resolves to the
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
    """The name a literal call claims, raising when the same module also binds it.

    The constant registry ties documents to the binding, so a module holding both forms could move
    the literal alone and leave those documents restating a name nothing writes.
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
    """The logger name one ``getLogger`` call claims, in whichever of the three forms it uses.

    A bare identifier is resolved against the module's own top level and nothing wider: a name
    imported from elsewhere raises, since following one would make this reader an importer of the
    brain, which is the seam the architecture keeps shut.
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
