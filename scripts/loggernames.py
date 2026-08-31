"""Which module owns a logger name, read out of the brain's source rather than by importing it."""

import re
from pathlib import Path

from logcalls import LogCallError, modules, parsed, read
from moduleconstants import constants

GET_LOGGER = re.compile(
    r"getLogger\(\s*(?:__name__|\"(?P<named>[^\"]+)\"|(?P<bound>[A-Za-z_]\w*))\s*\)"
)

# `cortex_core/__init__.py` is the logger `cortex_core`, not `cortex_core.__init__`.
PACKAGE_MODULE = "__init__"


def dotted(relative: Path) -> str:
    """The dotted name `__name__` holds for a module at ``relative`` inside its source root."""
    parts = relative.with_suffix("").parts
    if parts[-1] == PACKAGE_MODULE:
        parts = parts[:-1]
    return ".".join(parts)


def _literal(named: str, text: str, shown: str) -> str:
    """The name a literal call claims, raising when the same module also binds it."""
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
    """The logger name one ``getLogger`` call claims, in whichever of the three forms it uses."""
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
