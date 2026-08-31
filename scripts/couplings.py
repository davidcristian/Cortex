"""The types a registry entry for `crosscheck.py` is written with."""

from enum import Enum
from typing import NamedTuple

PLACEHOLDER = "{value}"

NAME_PLACEHOLDER = "{name}"


class Relation(Enum):
    """How the values at a constant's sites must relate to each other."""

    EQUAL = "identical"
    ORDERED = "non-decreasing in registry order"
    MEMBER = "members of the collection the last site declares"


class Spelling(Enum):
    """How a mention writes the agreed value down, where the far side's syntax differs."""

    WRITTEN = "as the declaring site writes it"
    WHOLE = "as a whole number, which the declared value must be"
    LOWERED = "in the lower case another language writes the same word in"

    @property
    def lossy(self) -> bool:
        """Whether two different declared values can render as the same text."""
        return self is Spelling.WHOLE


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it."""

    path: str
    name: str


class Mention(NamedTuple):
    """One place that uses a value without declaring it, and the form it appears in."""

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
