r"""The characters a URL parser *removes* from its input, behind the output guardrail (ADR-0015).

Its own module for the reason ``url_confusables`` is: a responsibility, not a size. Both halves of
the defense need this table and neither may own it. The **grammar** (``urls``) must admit the
character, since a URL carrying one is a URL and the matcher runs before any normalization, so a
spelling it does not admit anchors nothing and both policies are blind to it. The **identity**
(``url_identity``) must drop it, so the odd spelling and the plain one are one link. Spelling it in
either module would put the other's import in a cycle, so it is spelled here and both read it.

The reading is the URL Standard's own, the tenth addendum's question answered by the parser rather
than by a resemblance: **before it parses anything, the basic URL parser removes all ASCII tab and
newline from its input**, at every position, so `http://evil.exa<TAB>mple/pay` IS
`http://evil.example/pay` to every conforming parser, the browser the user pastes into included
(measured in ``node``). The overlay renders a reply with ``white-space: pre-wrap``, so the character
survives to the clipboard exactly as written.

Of the three the standard names, only the **tab** is admitted, and the line break is declined on the
twelfth addendum's own sentence, now with a number attached: a newline is where a wrapped sentence
breaks, and admitting one extends 42 spans over the repo's own prose (a link at a line's end
swallowing the next line's first word), against zero for the tab (ADR-0015 fifteenth addendum).

Deterministic and dependency-free (stdlib only). Pure state- and I/O-free.
"""

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
    """``literal`` as a regex tolerating a removal between any two of its characters.

    The parser's sentence reaching the second half of this grammar (ADR-0015 seventeenth addendum).
    The body admitted the character on its own, but every *literal* around it still read as
    characters in a fixed order, so a scheme word, a separator token and a bracketed defang token
    each declined a character the parser deletes before it reads any of them: `ht<TAB>tp` is
    `http`, and `[d<TAB>ot]` is `[dot]`. Generated per character rather than listed, the
    ``_prefixes`` precedent, so a token's tabbed forms cannot drift from the token.

    This is also the answer to where the removal sits relative to the refanger, which the body
    position never had to ask. It does not move: the fold still runs *after* the gap fold, so a gap
    spelled with tabs keeps the reader's reading, and the refanger stops caring where a removal
    stands by spelling its own literals through here instead.

    One family is deliberately **not** built this way, and the line is the ninth addendum's: an
    HTML character reference is admitted because *one rendering pass* resolves it, and no renderer
    resolves ``&#5<TAB>8;``. So the junctions around a reference are permeable and its digits are
    not, which is why the two are generated separately.
    """
    return REMOVED_RUN.join(re.escape(char) for char in literal)


def strip_removed(url: str) -> str:
    """Drop the characters a URL parser removes from its input (``REMOVED``) from an identity.

    Run **after** the gap fold rather than before it, which is the one ordering decision here: a
    host spelled `evil<TAB>dot<TAB>com` has two readings, the reader's (who refangs the gap and
    types `evil.com`) and the parser's (which removes the tabs and reads `evildotcom`). The identity
    takes the reader's, because that is the reading the whole defang family rests on, and because
    the parser's names a host that has to be separately registered to be an attack at all and so is
    no laundering of the collected link.
    """
    return url.translate(_REMOVALS)
