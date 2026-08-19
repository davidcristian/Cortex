"""The vocabulary the registry `crosscheck.py` reads is written in: what a coupling may say.

Split out of the scan, which is all of the logic; the two files beside this one are all of the
data, and they grow every time a coupling is found. `seamcouplings.py` holds the entries that tie
the body to the brain, and the brain to the stack and the runbooks that ship its numbers;
`overlaycouplings.py` holds the ones that tie the overlay's TypeScript to its own stylesheet. Both
moved out as the one file outgrew the 300-line cap, and `crosscheck.py` walks them as one registry.
Each entry carries the reason its places must agree, printed with any failure, because a gate that
says only "these differ" leaves the reader to rediscover why they must not.

**Two kinds of far side**, and the difference is what a rename has to walk past:

- A **site** DECLARES the value, so the scan reads it out and compares it. Both sides being
  declarations is the original case (`MAX_CAPTURE_BYTES` against `MAX_IMAGE_BYTES`).
- A **mention** SPENDS the value without declaring it: a metadata key spelled inside a shell
  string in a compose healthcheck, a custom property a stylesheet reads back with `var(...)`, a
  bare literal a component compares against. There is no declaration there to parse, so the scan
  renders the agreed value into the mention's template and requires the result to appear in the
  file. That is not circular: the template carries the SHAPE (`var({value},`) and the value comes
  from the declaring site, so a rename on either side leaves the rendered needle unfound. It is
  also why a bare literal does not have to be promoted to a named constant first.

Where the far side NAMES the value rather than restating it, the mention carries that name and the
template renders it: a stylesheet that declares `--roll: 300ms` and pays it as `var(--roll)` writes
the number once and the name three times, and only the first of those is something a rendered value
could reach. So the pair is written as two mentions of one entry, `{name}: {value}ms;` holding the
declaration and `var({name})` holding the spends, and the registry refuses a name pinned as a spend
that no mention of the same entry pays a value under, which would hold the name and quietly drop
the value.

A mention is a presence check by default: one bounded occurrence satisfies it however many the
file spends, so a half applied rename that updates one of two identical comparisons leaves the
gate green with the other one dead. `occurrences` closes that where a mention's several
occurrences are one set, pinning an EXACT count rather than a floor. It is opt in on purpose: a
floor cannot notice it has gone stale, and a count over a far side whose occurrences are
independent of each other is arithmetic that reddens on every unrelated addition. Set it only
where losing one occurrence is a defect rather than a design change.

**`Relation`** says how a constant's sites must stand to each other. Most couplings are
equalities. A few are orderings, where one side's bound has to sit under another's rather than
equal it, and an ordering compares integers only. One is a membership, where the value one tree
produces has to be one of the several another tree accepts, which is neither an equality nor an
ordering: the collection is the whole point, and the last site is the one that declares it.
"""

from enum import Enum
from typing import NamedTuple

# What a mention's template substitutes. A template rendering neither this nor the name below
# would tie nothing and is refused.
PLACEHOLDER = "{value}"

# What a mention's template substitutes for the name the far side spends the value under. A
# template may render the value, the name, or both; a mention carries a name exactly when its
# template renders one, either half of that being dead data the scan refuses.
NAME_PLACEHOLDER = "{name}"


class Relation(Enum):
    """How the values at a constant's sites must stand to each other."""

    EQUAL = "identical"
    ORDERED = "non-decreasing in registry order"
    MEMBER = "members of the collection the last site declares"


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it."""

    path: str
    name: str


class Mention(NamedTuple):
    """One place that spends a value without declaring it, and the shape it appears in.

    ``occurrences`` unset asks only that the rendered needle appear. Set, it asks that it appear
    exactly that many times, for a far side whose several occurrences must move together.

    ``name`` is the name that far side spends the value under, rendered wherever the template
    carries the name placeholder. It is the only thing that reaches a spend the value never
    appears in, and it is set exactly when the template renders one.
    """

    path: str
    template: str
    occurrences: int | None = None
    name: str | None = None


class Constant(NamedTuple):
    """One value every site and mention must hold in common, and why they must."""

    label: str
    why: str
    sites: tuple[Site, ...]
    relation: Relation = Relation.EQUAL
    mentions: tuple[Mention, ...] = ()
