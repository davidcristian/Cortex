"""Repo gate: fail when one value spelled in two trees stops agreeing with itself.

A few constants exist twice, once per language, because both sides of the seam must hold the same
number or the same string and neither toolchain can import the other's. Each side pins its own
literal in its own suite, which catches an edit to the constant alone. What nothing caught is an
edit to a constant and its own pin together: both suites stay green while the two trees disagree.

This file is the logic and reports the constants that do not tie. The registry it reads is
`registry.py`, which names the `*couplings.py` data files; the vocabulary those are written in is
`couplings.py`, what a value reduces to is `values.py`, what it means for a constant's readings to
hold together is `readings.py`, and how a rendered needle is looked for is `needles.py`.

ADR-0029's cross-language-constant addenda argue the rest: why the sites are compared with each
other rather than against a designated master, why a constant the scan cannot find, cannot read,
finds twice, or cannot reduce fails rather than passing, why `Mention.occurrences` pins an exact
count rather than a floor, and why a far side whose syntax cannot take the value as written is
reached by re-spelling rather than by a second number in the registry.

The success line states the registry's own shape, entries over sites over mentions and how many of
those mentions pin a count, because that is the collection every mutation table in this repo opens
by naming. It is a reading and never an assertion: holding the documents that quote it to it would
tie this gate's prose to this gate's own data.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

from couplings import (
    NAME_PLACEHOLDER,
    PLACEHOLDER,
    Constant,
    Mention,
    Relation,
    Site,
)
from needles import bounded, unfound
from readings import Reading, relation_fault
from registry import CONSTANTS, shape
from values import CrossCheckError, Value, parse_value, spell, spelling_fault

# A registry entry naming one place would agree with itself forever. Two is therefore the floor,
# and it counts mentions: a lone declaration plus one place that spends it is a real coupling.
MIN_PLACES = 2

# The floor under a pinned occurrence count. Zero would ask a mention to prove the value is
# absent, which is the opposite of a coupling, and a negative count asks nothing at all.
MIN_OCCURRENCES = 1

# One declaration syntax per language, each matching only a module-level (Python, TypeScript) or
# item-level (Rust) constant, and each capturing exactly the value expression. `{name}` is
# substituted with the escaped identifier. An unknown suffix is a fault rather than a skip. The
# TypeScript form is anchored at column 0 like the Python one, so a `const` inside a function is a
# local and not a second declaration of the module's constant; its type annotation is optional
# because TypeScript infers one, where Rust requires it. The Python form captures either the rest
# of the declaration's line or, when that line ends in an opening parenthesis, the whole run down
# to the line that closes it, which is the shape `values.py` reduces as a block; a run that never
# closes falls back to the one-line capture and is refused there.
DECLARATIONS = {
    ".py": (
        r"^{name}(?:\s*:[^=\n]*)?\s*=(?P<value>[ \t]*\([ \t]*(?:#[^\n]*)?\n"
        r"(?:(?![ \t]*\))[^\n]*\n)*[ \t]*\)[^\n]*|[^\n]*)$"
    ),
    ".rs": (
        r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+)?(?:const|static)[ \t]+{name}"
        r"[ \t]*:[^=\n]*=(?P<value>[^;\n]*);"
    ),
    ".ts": r"^(?:export[ \t]+)?const[ \t]+{name}(?:[ \t]*:[^=\n]*)?[ \t]*=(?P<value>[^;\n]*);",
}


class Fault(NamedTuple):
    """One constant that is not tied: a place that cannot be read, or places that disagree."""

    label: str
    detail: str


def _read(root: Path, path: str) -> str:
    """Return one registered file's text, or raise when it cannot be read."""
    try:
        return (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise CrossCheckError(msg) from err


def read_value(root: Path, site: Site) -> Value:
    """Return the value ``site`` declares under ``root``, or raise when it cannot be read."""
    template = DECLARATIONS.get(Path(site.path).suffix)
    if template is None:
        msg = f"no declaration syntax is known for {site.path}"
        raise CrossCheckError(msg)
    text = _read(root, site.path)
    pattern = re.compile(template.replace("{name}", re.escape(site.name)), re.MULTILINE)
    found: list[str] = pattern.findall(text)
    if not found:
        msg = f"{site.path} declares no {site.name}"
        raise CrossCheckError(msg)
    if len(found) > 1:
        msg = f"{site.path} declares {site.name} {len(found)} times"
        raise CrossCheckError(msg)
    return parse_value(found[0])


def rendered(mention: Mention, value: Value) -> str:
    """The text a mention pins: its template with the agreed value and its own name rendered in."""
    renders_name = NAME_PLACEHOLDER in mention.template
    if PLACEHOLDER not in mention.template and not renders_name:
        msg = (
            f"mention {mention.template!r} renders neither {PLACEHOLDER} nor "
            f"{NAME_PLACEHOLDER}, so it ties nothing"
        )
        raise CrossCheckError(msg)
    if renders_name and mention.name is None:
        msg = f"mention {mention.template!r} renders a name the mention does not carry"
        raise CrossCheckError(msg)
    if mention.name is not None and not renders_name:
        msg = (
            f"mention {mention.template!r} carries the name {mention.name!r} and renders it nowhere"
        )
        raise CrossCheckError(msg)
    spelled = mention.template.replace(PLACEHOLDER, spell(value, mention.spelling))
    return spelled if mention.name is None else spelled.replace(NAME_PLACEHOLDER, mention.name)


def check_mention(root: Path, mention: Mention, value: Value) -> None:
    """Raise unless the file spends ``value`` in the shape, and the number, the mention names."""
    wanted = mention.occurrences
    if wanted is not None and wanted < MIN_OCCURRENCES:
        msg = f"mention {mention.template!r} pins {wanted} occurrences, which ties nothing"
        raise CrossCheckError(msg)
    needle = rendered(mention, value)
    text = _read(root, mention.path)
    found = len(bounded(needle).findall(text))
    if wanted is None:
        if not found:
            msg = unfound(mention, needle, text, spell(value, mention.spelling))
            raise CrossCheckError(msg)
    elif found != wanted:
        msg = (
            f"{mention.path} spells {needle!r} as a token of its own: found {found}, pinned "
            f"{wanted}; move the whole set, or correct occurrences in the registry"
        )
        raise CrossCheckError(msg)


def registry_fault(constant: Constant) -> str | None:
    """The complaint about how a registry entry is written, or None when it can tie anything."""
    if not constant.sites:
        return "names no declaring site, so nothing establishes its value"
    if len(constant.sites) + len(constant.mentions) < MIN_PLACES:
        return "names fewer than two places, so it compares nothing"
    if constant.relation is not Relation.EQUAL and constant.mentions:
        return f"is {constant.relation.value}, so it has no one value a mention could spell"
    return spelling_fault(constant) or spend_fault(constant)


def spend_fault(constant: Constant) -> str | None:
    """The complaint about a name pinned as a spend that nothing pays the value under.

    A site pays the name it declares: reading the declaration is reading the value under that
    name, which is what a mention rendering both placeholders does on a far side the scan has no
    declaration syntax for. So a spend is paid by either kind of place.
    """
    paid = {site.name for site in constant.sites}
    paid |= {
        mention.name
        for mention in constant.mentions
        if mention.name is not None and PLACEHOLDER in mention.template
    }
    for mention in constant.mentions:
        if mention.name is None or PLACEHOLDER in mention.template or mention.name in paid:
            continue
        return (
            f"spends {mention.name!r} where no site declares that name and no mention renders "
            "the value under it, so the spend is held and the declaration it pays is not"
        )
    return None


def check_constant(root: Path, constant: Constant) -> list[Fault]:
    """Return every fault for one constant: unreadable places first, then how they relate."""
    written = registry_fault(constant)
    if written is not None:
        return [Fault(label=constant.label, detail=written)]
    values: list[Reading] = []
    faults: list[Fault] = []
    for site in constant.sites:
        try:
            values.append((site, read_value(root, site)))
        except CrossCheckError as err:
            faults.append(Fault(label=constant.label, detail=str(err)))
    if faults:
        return faults
    detail = relation_fault(constant, values)
    if detail is not None:
        return [Fault(label=constant.label, detail=f"{detail}; {constant.why}")]
    for mention in constant.mentions:
        try:
            check_mention(root, mention, values[0][1])
        except CrossCheckError as err:
            faults.append(Fault(label=constant.label, detail=f"{err}; {constant.why}"))
    return faults


def check(root: Path, constants: tuple[Constant, ...] | None = None) -> list[Fault]:
    """Check every registered constant under ``root``, in registry order."""
    registry = CONSTANTS if constants is None else constants
    return [fault for constant in registry for fault in check_constant(root, constant)]


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a constant spelled in two trees stops agreeing with itself.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the declaring trees (default: current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"crosscheck: root {root} is not a directory", file=sys.stderr)
        return 2
    faults = check(root)
    for fault in faults:
        print(f"{fault.label}: {fault.detail}")
    if faults:
        print(
            f"\ncrosscheck: {len(faults)} cross-tree constant(s) are not tied. Change every "
            "place together, or update the registry beside this scan if one of them moved.",
            file=sys.stderr,
        )
        return 1
    size = shape(CONSTANTS)
    print(
        f"crosscheck OK: {size.entries} cross-tree constant(s) under {root} agree, "
        f"over {size.sites} declaring site(s) and {size.mentions} mention(s), "
        f"{size.counted} of them pinned to a count"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
