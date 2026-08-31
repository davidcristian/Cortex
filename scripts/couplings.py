"""The types a registry entry for `crosscheck.py` is written with.

This module is the vocabulary; the `*couplings.py` files beside it are the entries, split across
several files by the 300-line cap and named by `registry.py` so the scan walks them as one
registry. Each entry carries the reason its places must agree, which is printed with any failure.
The registry's design is argued in the ADR-0029 cross-language-constant addendum and in
`docs/modules/repo-gates.md`.

Two kinds of far side, and the distinction is used throughout this tree:

- A **site** DECLARES the value, so the scan reads it out and compares it. Both sides being
  declarations is the original case (`MAX_CAPTURE_BYTES` against `MAX_IMAGE_BYTES`).
- A **mention** SPENDS the value without declaring it: a metadata key written inside a shell
  string in a compose healthcheck, a custom property a stylesheet reads back with `var(...)`, a
  bare literal a component compares against. There is no declaration to parse, so the scan renders
  the agreed value into the mention's template and requires the result to appear in the file. The
  template carries only the shape (`var({value},`) and the value comes from the declaring site, so
  a rename on either side leaves the rendered needle unfound. It is also why a bare literal does
  not have to be promoted to a named constant first.

Where the far side NAMES the value rather than restating it, the mention carries that name and the
template renders it: a stylesheet declaring `--roll: 300ms` and paying it as `var(--roll)` writes
the number once and the name three times, and only the first is reachable by a rendered value. The
pair is written as two mentions of one entry, `{name}: {value}ms;` for the declaration and
`var({name})` for the spends, and the registry rejects a name pinned as a spend that no mention of
the same entry pays a value under, which would hold the name and drop the value.

A mention is a presence check by default: one bounded occurrence satisfies it however many times
the file spends the value, so a half applied rename that updates one of two identical comparisons
leaves the gate green. `occurrences` pins an exact count instead, and is opt in because a count
over a far side whose occurrences are independent fails on every unrelated addition. Set it only
where losing one occurrence is a defect rather than a design change.
"""

from enum import Enum
from typing import NamedTuple

# What a mention's template substitutes. A template rendering neither this nor the name below
# ties nothing, and the scan fails on one.
PLACEHOLDER = "{value}"

# What a mention's template substitutes for the name the far side spends the value under. A
# template may render the value, the name, or both; a mention carries a name exactly when its
# template renders one, either half without the other being dead data the scan fails on.
NAME_PLACEHOLDER = "{name}"


class Relation(Enum):
    """How the values at a constant's sites must stand to each other.

    Most couplings are equalities. An ordering compares integers only. A membership asks that every
    other site's value be in the collection the last site declares.
    """

    EQUAL = "identical"
    ORDERED = "non-decreasing in registry order"
    MEMBER = "members of the collection the last site declares"


class Spelling(Enum):
    """How a mention writes the agreed value down, where the far side's syntax differs.

    Each spelling is derived from the declared value rather than typed into the registry, and
    raises on any value it would have to change to fit. ``WRITTEN`` is the site's own text.
    ``WHOLE`` drops a fractional part a syntax will not take, docker reading `8g` as a size and
    rejecting `8.0g`, and raises when that fraction is not zero. ``LOWERED`` folds a boolean's word
    to the case another language writes it in, Python declaring `False` where YAML writes `false`.
    """

    WRITTEN = "as the declaring site writes it"
    WHOLE = "as a whole number, which the declared value must be"
    LOWERED = "in the lower case another language writes the same word in"

    @property
    def lossy(self) -> bool:
        """Whether two declared values may render alike, which is what needs a reading beside it.

        A whole spelling may, `8` and `8.0` being one whole number. A case fold may not, `False`
        and `True` lowering to two different words.
        """
        return self is Spelling.WHOLE


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it.

    The identifier is a name a file declares, never a name a module exports, so a module-private
    one is registered under its underscore (`_UNRESTRICTED_REASONING`). The scan reads text and
    imports nothing, so naming a private constant asks nothing of the module; widening an API to
    suit the gate would edit the contract the gate watches. A rename the registry is not told about
    fails the scan rather than passing silently, since a place that cannot be read is a fault.
    """

    path: str
    name: str


class Mention(NamedTuple):
    """One place that spends a value without declaring it, and the shape it appears in.

    ``occurrences`` unset asks only that the rendered needle appear; set, it asks that it appear
    exactly that many times. ``name`` is the name the far side spends the value under, rendered
    wherever the template carries the name placeholder, and set exactly when it does. ``spelling``
    is how the value is written into the template, defaulting to the site's own text.
    """

    path: str
    template: str
    occurrences: int | None = None
    name: str | None = None
    spelling: Spelling = Spelling.WRITTEN


class Constant(NamedTuple):
    """One value every site and mention must hold in common, and why they must."""

    label: str
    why: str
    sites: tuple[Site, ...]
    relation: Relation = Relation.EQUAL
    mentions: tuple[Mention, ...] = ()
