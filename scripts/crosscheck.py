"""Fail when one value written in more than one place stops agreeing with itself."""

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
from linereadings import counted, short
from readings import Reading, relation_fault
from registry import CONSTANTS, shape
from searchtexts import bounded, unfound
from values import CrossCheckError, Value, parse_value, spell, spelling_fault

# Two places is the minimum: a value written once always agrees with itself.
MIN_PLACES = 2

MIN_OCCURRENCES = 1

RECOUNT = "move the whole set, or correct occurrences in the registry"

# One declaration form per language. `{name}` is replaced with the constant's name before the
# search, and the `value` group is the value expression.
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
    """One constant with a problem: a place that cannot be read, or places that disagree."""

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
    """The text a mention asks for: its template with the value and the name filled in."""
    renders_name = NAME_PLACEHOLDER in mention.template
    if PLACEHOLDER not in mention.template and not renders_name:
        msg = (
            f"mention {mention.template!r} renders neither {PLACEHOLDER} nor "
            f"{NAME_PLACEHOLDER}, so it ties nothing"
        )
        raise CrossCheckError(msg)
    if renders_name and mention.name is None:
        msg = f"mention {mention.template!r} renders a name the mention does not have"
        raise CrossCheckError(msg)
    if mention.name is not None and not renders_name:
        msg = f"mention {mention.template!r} has the name {mention.name!r} and renders it nowhere"
        raise CrossCheckError(msg)
    spelled = mention.template.replace(PLACEHOLDER, spell(value, mention.spelling))
    return spelled if mention.name is None else spelled.replace(NAME_PLACEHOLDER, mention.name)


def check_mention(root: Path, mention: Mention, value: Value) -> None:
    """Raise unless the file contains ``value`` in the form, and as often, as the mention says."""
    wanted = mention.occurrences
    if wanted is not None and wanted < MIN_OCCURRENCES:
        msg = f"mention {mention.template!r} sets {wanted} occurrences, which ties nothing"
        raise CrossCheckError(msg)
    needle = rendered(mention, value)
    text = _read(root, mention.path)
    pattern = bounded(needle)
    matches = list(pattern.finditer(text))
    found = len(matches)
    if not found:
        reading = unfound(mention, needle, text, spell(value, mention.spelling))
        tail = "" if wanted is None else f"; the registry sets {wanted} occurrences, so {RECOUNT}"
        msg = f"{reading}{tail}"
        raise CrossCheckError(msg)
    if wanted is not None and found != wanted:
        rest = short(needle, text, pattern) if found < wanted else ""
        msg = (
            f"{mention.path} writes {needle!r} as a token of its own: found {found}"
            f"{counted(text, matches)}, set to {wanted}{rest}; {RECOUNT}"
        )
        raise CrossCheckError(msg)


def registry_fault(constant: Constant) -> str | None:
    """What is wrong with how a registry entry is written, or None when it can be checked."""
    if not constant.sites:
        return "names no declaring site, so nothing establishes its value"
    if len(constant.sites) + len(constant.mentions) < MIN_PLACES:
        return "names fewer than two places, so it compares nothing"
    if constant.relation is not Relation.EQUAL and constant.mentions:
        return f"is {constant.relation.value}, so it has no one value a mention could write"
    return spelling_fault(constant) or spend_fault(constant)


def spend_fault(constant: Constant) -> str | None:
    """What is wrong when a mention uses a name nothing declares the value under, or None."""
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
    """Return every fault for one constant: unreadable places first, then disagreements."""
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
    """Run the check; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a constant written in two trees stops agreeing with itself.",
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
        f"{size.counted} of them held to a count"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
