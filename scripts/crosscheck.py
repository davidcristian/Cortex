"""Repo gate: fail when one value declared in two trees stops agreeing with itself.

A few constants exist twice, once per language, because both sides of the seam must hold
the same number or the same string and neither toolchain can import the other's. Each side
already pins its own literal in its own suite, which catches an edit to the constant alone.
What nothing caught is an edit to a constant **and** its own pin: both suites stay green
while the two trees disagree. That is the drift this gate closes.

**No master.** proto/body.proto is the source of truth for the seam's *shape*, but protobuf
has no constant, so a value could only live there as a comment, and a comment is one more
uncoupled copy: the 1600 px default edge is already spelled in four places, one of them a
proto comment. So this gate compares the sites with each other rather than against a
designated original, which is what keeps it symmetric. A designated original would leave that
one file editable alone, which is the same drift with the roles reversed.

**Fail closed** is the whole point. A constant this scan cannot find, cannot read, finds
twice, or cannot reduce to a value is a failure, never a silent pass, because a rename that
quietly emptied the registry would leave a scan that always agrees with itself.

A value is compared after reduction, not as text, so one site may write ``6291456`` where
another writes ``6 * 1024 * 1024``. Two forms reduce: a product of integer literals, and a
plain double-quoted string. Anything else is refused rather than guessed at.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# The only comment marker a declaration's right-hand side may carry. Rust needs none: its
# value is captured up to the terminating semicolon, so a trailing `//` never arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# A registry entry naming one site would agree with itself forever, which is the gate that
# cannot fail this scan was written to remove. Two is therefore the floor, not a formality.
MIN_SITES = 2

# One declaration syntax per language, each matching only a module-level (Python) or item-level
# (Rust) constant, and each capturing exactly the value expression. `{name}` is substituted with
# the escaped identifier. An unknown suffix is a fault, never a skip.
DECLARATIONS = {
    ".py": r"^{name}(?:\s*:[^=\n]*)?\s*=(?P<value>[^\n]*)$",
    ".rs": (
        r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+)?(?:const|static)[ \t]+{name}"
        r"[ \t]*:[^=\n]*=(?P<value>[^;\n]*);"
    ),
}


class CrossCheckError(Exception):
    """A constant's value could not be established at one site."""


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it."""

    path: str
    name: str


class Constant(NamedTuple):
    """One value that must be identical at every site declaring it, and why it must be."""

    label: str
    why: str
    sites: tuple[Site, ...]


class Fault(NamedTuple):
    """One constant that is not tied: a site that cannot be read, or sites that disagree."""

    label: str
    detail: str


CONSTANTS: tuple[Constant, ...] = (
    Constant(
        label="the screen-capture byte ceiling",
        why=(
            "the brain sends its own budget as the capture request's max_bytes and re-verifies "
            "it on receipt, so a body ceiling above the brain's would let a capture pass the "
            "body and be refused in the brain (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_CAPTURE_BYTES"),
            Site("brain/packages/core/src/cortex_core/images.py", "MAX_IMAGE_BYTES"),
        ),
    ),
    Constant(
        label="the seam token's metadata key",
        why=(
            "each side attaches the token under this key and the other reads it back out, in "
            "both seam directions, so a disagreement fails every authenticated call (ADR-0016)"
        ),
        sites=(
            Site("body/crates/rpc/src/auth.rs", "SEAM_TOKEN_HEADER"),
            Site("body/crates/rpc/src/client.rs", "SEAM_TOKEN_HEADER"),
            Site("brain/packages/seam/src/cortex_seam/__init__.py", "SEAM_TOKEN_HEADER"),
        ),
    ),
)


def _string_value(text: str) -> str:
    """Read one double-quoted literal, tolerating only a trailing comment after it."""
    end = text.find('"', 1)
    if end < 0:
        msg = f"unterminated string literal in {text!r}"
        raise CrossCheckError(msg)
    literal = text[1:end]
    if "\\" in literal:
        msg = f"escapes are not decoded, so {text!r} cannot be compared"
        raise CrossCheckError(msg)
    trailer = text[end + 1 :].strip()
    if trailer and not trailer.startswith(COMMENT_MARKER):
        msg = f"{text!r} is more than one string literal"
        raise CrossCheckError(msg)
    return literal


def _integer_value(text: str) -> int:
    """Reduce a product of integer literals, so `6 * 1024 * 1024` compares as 6291456."""
    expression = text.partition(COMMENT_MARKER)[0].strip()
    if not INTEGER_PRODUCT.match(expression):
        msg = f"{text!r} is neither a string literal nor a product of integers"
        raise CrossCheckError(msg)
    product = 1
    for factor in expression.split("*"):
        product *= int(factor.replace("_", ""))
    return product


def parse_value(text: str) -> str | int:
    """Reduce a declaration's right-hand side to a value two languages compare on."""
    stripped = text.strip()
    if stripped.startswith('"'):
        return _string_value(stripped)
    return _integer_value(stripped)


def read_value(root: Path, site: Site) -> str | int:
    """Return the value ``site`` declares under ``root``, or raise when it cannot be read."""
    template = DECLARATIONS.get(Path(site.path).suffix)
    if template is None:
        msg = f"no declaration syntax is known for {site.path}"
        raise CrossCheckError(msg)
    try:
        text = (root / site.path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {site.path}: {err}"
        raise CrossCheckError(msg) from err
    pattern = re.compile(template.replace("{name}", re.escape(site.name)), re.MULTILINE)
    found: list[str] = pattern.findall(text)
    if not found:
        msg = f"{site.path} declares no {site.name}"
        raise CrossCheckError(msg)
    if len(found) > 1:
        msg = f"{site.path} declares {site.name} {len(found)} times"
        raise CrossCheckError(msg)
    return parse_value(found[0])


def check_constant(root: Path, constant: Constant) -> list[Fault]:
    """Return every fault for one constant: unreadable sites if any, else a disagreement."""
    if len(constant.sites) < MIN_SITES:
        detail = "names fewer than two sites, so it compares nothing"
        return [Fault(label=constant.label, detail=detail)]
    values: list[tuple[Site, str | int]] = []
    faults: list[Fault] = []
    for site in constant.sites:
        try:
            values.append((site, read_value(root, site)))
        except CrossCheckError as err:
            faults.append(Fault(label=constant.label, detail=str(err)))
    if faults:
        return faults
    if len({value for _, value in values}) > 1:
        shown = ", ".join(f"{site.path}: {site.name} = {value!r}" for site, value in values)
        detail = f"sites disagree ({shown}); {constant.why}"
        return [Fault(label=constant.label, detail=detail)]
    return []


def check(root: Path, constants: tuple[Constant, ...] | None = None) -> list[Fault]:
    """Check every registered constant under ``root``, in registry order."""
    registry = CONSTANTS if constants is None else constants
    return [fault for constant in registry for fault in check_constant(root, constant)]


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a constant declared in two trees stops agreeing with itself.",
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
            "site together, or update the registry in crosscheck.py if one of them moved.",
            file=sys.stderr,
        )
        return 1
    print(f"crosscheck OK: {len(CONSTANTS)} cross-tree constant(s) under {root} agree")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
