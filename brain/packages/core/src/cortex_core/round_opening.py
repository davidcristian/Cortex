"""Drop the opening sentences of a tool loop round that an earlier round of the reply wrote."""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# A first sentence ends at a stop and the white space after it, or at a line break, and is
# known to be whole only once the text after it begins.
_OPENING = re.compile(
    r"(?P<lead>\s*)(?P<sentence>\S[^\n]*?(?:[.!?](?=\s)|(?=\n)))(?P<gap>\s+)(?=\S)"
)
# A line with no letter, such as a list number, or one opening with markdown structure (a fence,
# a heading, a table row, a list item or a quote) is never dropped as a repeat.
_LETTER = re.compile(r"[^\W\d_]")
_STRUCTURE = re.compile(r"[|>]|`{3}|~{3}|(?:#{1,6}|[-*+]|\d+[.)])(?:\s|$)")


def _words(sentence: str) -> str:
    """``sentence`` with each run of white space as one space."""
    return " ".join(sentence.split())


class OpeningHold:
    """Hold one round's text while its opening sentences repeat, and drop each one that does."""

    def __init__(self, said: str) -> None:
        """``said`` is the text the earlier rounds of the reply streamed."""
        sentences = (_words(part) for part in _SENTENCE_END.split(said))
        self._earlier = frozenset(
            words for words in sentences if _LETTER.search(words) and not _STRUCTURE.match(words)
        )
        self._holding = bool(self._earlier)
        self._spaced = said[-1:].isspace()
        self._held = ""
        self._gap = ""

    def feed(self, text: str) -> str:
        """The text to stream now, which is empty while an opening sentence is still held."""
        if not self._holding:
            return text
        self._held += text
        while (found := _OPENING.match(self._held)) is not None:
            if _words(found["sentence"]) not in self._earlier:
                self._holding = False
                return self._gap + self._held
            # The white space after the first dropped sentence keeps the round apart from the
            # earlier text when neither that text's end nor this round's start has any.
            self._gap = self._gap or found["lead"] or ("" if self._spaced else found["gap"])
            self._held = self._held[found.end() :]
        return ""

    def flush(self) -> str:
        """What is still held when the round ends: nothing when it is only a repeated sentence."""
        if not self._holding:
            return ""
        self._holding = False
        return "" if _words(self._held) in self._earlier else self._gap + self._held
