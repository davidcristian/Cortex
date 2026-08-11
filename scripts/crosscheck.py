"""Repo gate: fail when one value spelled in two trees stops agreeing with itself."""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

from couplings import PLACEHOLDER, SEAM_COUPLINGS, Constant, Mention, Relation, Site
from overlaycouplings import OVERLAY_COUPLINGS
from values import CrossCheckError, Reading, Value, parse_value, relation_fault

CONSTANTS: tuple[Constant, ...] = (*SEAM_COUPLINGS, *OVERLAY_COUPLINGS)

# What counts as a continuation of a rendered needle's own token, at whichever of its two edges is
# itself made of one. A needle edged by punctuation (`var(--ceiling,`) needs no such guard.
WORD_CHARACTER = re.compile(r"\w")

# A registry entry naming one place would agree with itself forever, which is the gate that
# cannot fail this scan was written to remove. Two is therefore the floor, not a formality, and
# it counts mentions: a lone declaration plus one place that spends it is a real coupling.
MIN_PLACES = 2

# The floor under a pinned occurrence count. Zero would ask a mention to prove the value is
# ABSENT, which is the opposite of a coupling, and a negative one asks nothing at all.
MIN_OCCURRENCES = 1

DECLARATIONS = {
    ".py": r"^{name}(?:\s*:[^=\n]*)?\s*=(?P<value>[^\n]*)$",
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


def bounded(needle: str) -> re.Pattern[str]:
    """The needle as a pattern no longer token can contain: a word edge may not touch a word."""
    lead = r"(?<!\w)" if WORD_CHARACTER.match(needle[:1]) else ""
    trail = r"(?!\w)" if WORD_CHARACTER.match(needle[-1:]) else ""
    return re.compile(f"{lead}{re.escape(needle)}{trail}")


def check_mention(root: Path, mention: Mention, value: Value) -> None:
    """Raise unless the file spends ``value`` in the shape, and the number, the mention names."""
    if PLACEHOLDER not in mention.template:
        msg = f"mention {mention.template!r} carries no {PLACEHOLDER}, so it ties nothing"
        raise CrossCheckError(msg)
    wanted = mention.occurrences
    if wanted is not None and wanted < MIN_OCCURRENCES:
        msg = f"mention {mention.template!r} pins {wanted} occurrences, which ties nothing"
        raise CrossCheckError(msg)
    needle = mention.template.replace(PLACEHOLDER, str(value))
    found = len(bounded(needle).findall(_read(root, mention.path)))
    if wanted is None:
        if not found:
            msg = f"{mention.path} does not spell {needle!r} as a token of its own"
            raise CrossCheckError(msg)
    elif found != wanted:
        msg = (
            f"{mention.path} spells {needle!r} as a token of its own: found {found}, pinned "
            f"{wanted}; move the whole set, or correct occurrences in couplings.py"
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
            "place together, or update the registry in couplings.py if one of them moved.",
            file=sys.stderr,
        )
        return 1
    print(f"crosscheck OK: {len(CONSTANTS)} cross-tree constant(s) under {root} agree")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
