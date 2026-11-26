"""Read the rows a word for only limits a forget to, whatever other clause adds or keeps a row."""

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import LIMIT, run_role, runs

ONLY = forms.words(forms.ONLY)


def alone(query: str, value: str, named: frozenset[str]) -> set[str]:
    """The words of ``named`` in each run of ``query`` after ``value`` holding a word for only
    and read as a limit, as ``phone`` of ``Forget 4242, the card too, only the phone``."""
    found: set[str] = set()
    for run, _ in runs(query, value):
        words = named.intersection(run)
        if words and not ONLY.isdisjoint(run) and run_role(run, named) == LIMIT:
            found |= words
    return found
