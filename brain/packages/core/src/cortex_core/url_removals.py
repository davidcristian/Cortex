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

# The one character of the three that is admitted. Written as an escape so the source shows it
# rather than a blank the eye cannot tell from a space, the `_CONFUSABLES` convention.
REMOVED = "\t"

# The same table as a regex fragment, for the grammar's body character. Held here beside the
# string so the class the matcher admits and the characters the fold drops cannot drift.
REMOVED_CHARS = f"[{REMOVED}]"

_REMOVALS = str.maketrans(dict.fromkeys(REMOVED, None))


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
