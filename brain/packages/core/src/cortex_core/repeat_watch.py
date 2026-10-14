"""Finding a streamed reply that has started repeating one block of lines."""

import re
from collections import deque

__all__ = ["REPEATED_LINE_NOTE", "RepeatWatch"]

REPEATED_LINE_NOTE = (
    "\n\n(I stopped this answer because it started repeating the same line, so it is unfinished. "
    "Ask again, or ask in other words.)"
)

# The shape the reply loop readings judged: three back to back copies of one block of one to four
# lines, holding a line of at least 20 characters with a letter that the person's message lacks.
_COPIES = 3
_LONGEST_BLOCK = 4
_MIN_LINE_CHARS = 20
_LETTER = re.compile(r"[^\W\d_]")
_WORD = re.compile(r"[^\W_]+")


def _words(text: str) -> str:
    return " " + " ".join(_WORD.findall(text.lower())) + " "


class RepeatWatch:
    """Reads one reply as it streams and reports when one block of lines comes three times."""

    def __init__(self, query: str) -> None:
        self._query = _words(query)
        self._partial = ""
        self._recent: deque[str] = deque(maxlen=_COPIES * _LONGEST_BLOCK)

    def feed(self, text: str) -> bool:
        """Take the next piece of reply text and return whether the reply now repeats."""
        *complete, self._partial = (self._partial + text).split("\n")
        for line in complete:
            key = line.strip()
            if not key:
                continue
            self._recent.append(key)
            if any(self._repeats(size) for size in range(1, _LONGEST_BLOCK + 1)):
                return True
        return False

    def _repeats(self, size: int) -> bool:
        lines = list(self._recent)[-_COPIES * size :]
        if len(lines) < _COPIES * size:
            return False
        block = lines[:size]
        copies = [lines[k : k + size] for k in range(0, len(lines), size)]
        return all(copy == block for copy in copies) and any(map(self._counted, block))

    def _counted(self, line: str) -> bool:
        if len(line) < _MIN_LINE_CHARS or _LETTER.search(line) is None:
            return False
        return _words(line) not in self._query
