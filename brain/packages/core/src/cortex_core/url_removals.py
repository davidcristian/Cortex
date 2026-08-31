r"""The characters a URL parser removes from its input, behind the output guardrail."""

import re

# Of the three characters the URL Standard removes, only the tab is admitted. Admitting the
# line break extended 42 matches over this repo's own prose, a link at the end of a line
# swallowing the first word of the next, against none for the tab.
REMOVED = "\t"

REMOVED_CHARS = f"[{REMOVED}]"

REMOVED_RUN = f"{REMOVED_CHARS}*"

_REMOVALS = str.maketrans(dict.fromkeys(REMOVED, None))


def permeable(literal: str) -> str:
    """``literal`` as a regex tolerating a removal between any two of its characters."""
    return REMOVED_RUN.join(re.escape(char) for char in literal)


def strip_removed(url: str) -> str:
    """Drop the characters a URL parser removes from its input (``REMOVED``) from an identity."""
    # Run after the gap fold, not before it: a host written `evil<TAB>dot<TAB>com` has the
    # reader's reading, `evil.com`, and the parser's, `evildotcom`, and the identity takes the
    # reader's, which is the reading the whole defanging family rests on.
    return url.translate(_REMOVALS)
