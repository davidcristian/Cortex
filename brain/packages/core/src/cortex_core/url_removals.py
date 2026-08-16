r"""The characters a URL parser *removes* from its input, behind the output guardrail (ADR-0015)."""

# The one character of the three that is admitted. Written as an escape so the source shows it
# rather than a blank the eye cannot tell from a space, the `_CONFUSABLES` convention.
REMOVED = "\t"

# The same table as a regex fragment, for the grammar's body character. Held here beside the
# string so the class the matcher admits and the characters the fold drops cannot drift.
REMOVED_CHARS = f"[{REMOVED}]"

_REMOVALS = str.maketrans(dict.fromkeys(REMOVED, None))


def strip_removed(url: str) -> str:
    """Drop the characters a URL parser removes from its input (``REMOVED``) from an identity."""
    return url.translate(_REMOVALS)
