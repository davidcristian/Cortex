r"""The characters a URL parser *removes* from its input, behind the output guardrail (ADR-0015)."""

import re

# The one character of the three that is admitted. Written as an escape so the source shows it
# rather than a blank the eye cannot tell from a space, the `_CONFUSABLES` convention.
REMOVED = "\t"

# The same table as a regex fragment, for the grammar's body character. Held here beside the
# string so the class the matcher admits and the characters the fold drops cannot drift.
REMOVED_CHARS = f"[{REMOVED}]"

# A run of them, which is what may stand between any two characters of a literal below, and
# what a caller spells at a junction `permeable` cannot see: between a bracket and the token it
# wraps, or between a scheme word and its separator.
REMOVED_RUN = f"{REMOVED_CHARS}*"

_REMOVALS = str.maketrans(dict.fromkeys(REMOVED, None))


def permeable(literal: str) -> str:
    """``literal`` as a regex tolerating a removal between any two of its characters."""
    return REMOVED_RUN.join(re.escape(char) for char in literal)


def strip_removed(url: str) -> str:
    """Drop the characters a URL parser removes from its input (``REMOVED``) from an identity."""
    return url.translate(_REMOVALS)
