"""How the values read at one constant's sites must relate to each other."""

from itertools import pairwise

from couplings import Constant, Relation, Site
from values import Value

type Reading = tuple[Site, Value]


def _member_fault(readings: list[Value], shown: str, generic: str) -> str | None:
    """A membership passes when every value but the last is in the collection the last one is."""
    *produced, accepted = readings
    if not isinstance(accepted, frozenset):
        return (
            "a membership needs a collection at the last site, and that site declares a lone "
            f"value ({shown})"
        )
    return None if all(value in accepted for value in produced) else generic


def relation_fault(constant: Constant, values: list[Reading]) -> str | None:
    """What is wrong with how the read values relate, or None when they agree."""
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
