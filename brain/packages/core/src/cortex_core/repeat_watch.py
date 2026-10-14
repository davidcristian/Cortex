"""Finding a streamed reply that has started repeating one line."""

import re
from collections import Counter

__all__ = ["REPEATED_LINE_NOTE", "RepeatWatch"]

REPEATED_LINE_NOTE = (
    "\n\n(I stopped this answer because it started repeating the same line, so it is unfinished. "
    "Ask again, or ask in other words.)"
)

# The thresholds the reply loop readings judged: a line of at least 20 characters with a letter,
# arriving for the third time.
_MIN_LINE_CHARS = 20
_ARRIVALS = 3
_LETTER = re.compile(r"[^\W\d_]")


class RepeatWatch:
    """Reads one reply as it streams and reports when a line arrives for the third time."""

    def __init__(self) -> None:
        self._partial = ""
        self._seen: Counter[str] = Counter()

    def feed(self, text: str) -> bool:
        """Take the next piece of reply text and return whether a line has now repeated."""
        *complete, self._partial = (self._partial + text).split("\n")
        for line in complete:
            key = line.strip()
            if len(key) < _MIN_LINE_CHARS or _LETTER.search(key) is None:
                continue
            self._seen[key] += 1
            if self._seen[key] == _ARRIVALS:
                return True
        return False
