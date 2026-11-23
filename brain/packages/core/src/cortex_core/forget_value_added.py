"""Read a forget of a value that names stored rows after it only to add them to it."""

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import AND, FORGET, WHOSE, clauses

_ADD = forms.words(forms.ALSO)
_WELL = ["as", "well"]


def adds_to_value(query: str, value: str, named: frozenset[str]) -> bool:
    """Whether ``query`` is a forget verb, ``value``, then only words adding rows of ``named``, as
    ``Forget 4242, the card too``: a word for too or as well, or a word for and first."""
    tokens = [token for clause in clauses(query) for token in clause]
    wanted = [token for clause in clauses(value) for token in clause]
    size = len(wanted)
    at = next((i for i in range(len(tokens)) if size and tokens[i : i + size] == wanted), None)
    if at is None or not any(char.isdigit() for char in value):
        return False
    head, rest = tokens[:at], tokens[at + size :]
    plain = bool(head) and FORGET.fullmatch(head[0]) is not None and WHOSE.issuperset(head[1:])
    adds = not AND.isdisjoint(rest[:1]) or not _ADD.isdisjoint(rest) or rest[-2:] == _WELL
    read = named | WHOSE | AND | _ADD | frozenset(_WELL)
    return plain and adds and not named.isdisjoint(rest) and read.issuperset(rest)
