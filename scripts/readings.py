"""How the values read at one constant's sites must stand to each other.

Split out of `values.py` when the boolean and the signed integer brought that file to the 300-line
cap, on the seam its first paragraph had been drawing since it was written: one half says what a
declaration's right-hand side reduces to and how a mention may spell it, and this half says
whether a set of readings holds. Nothing here reads a file, and nothing here depends on where a
value lives; `crosscheck.py` finds the declarations and reports the faults this module returns.

Most couplings are equalities. ``ORDERED`` holds the sites to non-decreasing order, for the bounds
that must sit under one another rather than match, and it compares integers: a string, a decimal
and a boolean are each refused rather than guessed at, since `<=` over text would file ``10.0``
under ``9.0`` and an answer with two values has no order at all. ``MEMBER`` holds every site but
the last inside the collection the last one declares, which is the shape of a value one tree
produces and another tree accepts a set of: the two are not equal, neither is under the other, and
the only true thing to say about them is that one is in the other. Both read the registry's own
order, which is why an entry lists the bound before its ceiling and the value before its set.
"""

from itertools import pairwise

from couplings import Constant, Relation, Site
from values import Value

type Reading = tuple[Site, Value]


def _member_fault(readings: list[Value], shown: str, generic: str) -> str | None:
    """A membership holds when every reading but the last is in the collection the last one is."""
    *produced, accepted = readings
    if not isinstance(accepted, frozenset):
        return (
            "a membership needs a collection at the last site, and that site declares a lone "
            f"value ({shown})"
        )
    return None if all(value in accepted for value in produced) else generic


def relation_fault(constant: Constant, values: list[Reading]) -> str | None:
    """The complaint about how the read values stand to each other, or None when they hold."""
    shown = ", ".join(f"{site.path}: {site.name} = {value!r}" for site, value in values)
    generic = f"sites are not {constant.relation.value} ({shown})"
    readings = [value for _, value in values]
    if constant.relation is Relation.EQUAL:
        return None if len(set(readings)) == 1 else generic
    if constant.relation is Relation.MEMBER:
        return _member_fault(readings, shown, generic)
    numbers = [value for value in readings if isinstance(value, int)]
    if len(numbers) < len(readings):
        return f"an ordering compares integers, and a site here declares something else ({shown})"
    return None if all(lower <= upper for lower, upper in pairwise(numbers)) else generic
