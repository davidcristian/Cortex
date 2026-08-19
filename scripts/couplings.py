"""The vocabulary the registry `crosscheck.py` reads is written in: what a coupling may say."""

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


class Spelling(Enum):
    """How a mention writes the agreed value down, where the far side's syntax differs."""

    WRITTEN = "as the declaring site writes it"
    WHOLE = "as a whole number, which the declared value must be"


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it."""

    path: str
    name: str


class Mention(NamedTuple):
    """One place that spends a value without declaring it, and the shape it appears in."""

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
