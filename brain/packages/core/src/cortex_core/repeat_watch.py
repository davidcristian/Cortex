"""Finding a streamed reply that has started repeating one block of lines."""

import re
from collections import deque

__all__ = ["REPEATED_LINE_NOTE", "REPEATED_LINE_NOTES", "RepeatWatch"]

REPEATED_LINE_NOTE = (
    "\n\n(I stopped this answer because it started repeating the same line, so it is unfinished. "
    "Ask again, or ask in other words.)"
)
REPEATED_LINE_NOTES = {
    "fr": "\n\n(J'ai arrêté cette réponse parce qu'elle commençait à répéter la même ligne, elle "
    "est donc inachevée. Redemandez, ou demandez-le autrement.)",
    "de": "\n\n(Ich habe diese Antwort beendet, weil sie anfing, dieselbe Zeile zu wiederholen, "
    "sie ist also unvollständig. Fragen Sie erneut, oder fragen Sie mit anderen Worten.)",
    "es": "\n\n(Detuve esta respuesta porque empezó a repetir la misma línea, así que está sin "
    "terminar. Pregunta de nuevo, o pregúntalo con otras palabras.)",
    "ro": "\n\n(Am oprit acest răspuns pentru că începuse să repete același rând, așa că este "
    "neterminat. Întreabă din nou sau întreabă în alte cuvinte.)",
}

# The shape the reply loop readings judged: three back to back copies of a block of one to four
# lines with a counted line the message lacks. A count of copies in the message raises the three to
# one more than it, and a request for copies with no count to 13, the most that still stopped loops.
_COPIES = 3
_UNCOUNTED_COPIES = 13
_UNCOUNTED = (" again and again ", " over and over ", " keep repeating ")
_LONGEST_BLOCK = 4
_MIN_LINE_CHARS = 20
_LETTER = re.compile(r"[^\W\d_]")
_WORD = re.compile(r"[^\W_]+")
_UNITS = (
    *("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"),
    *("thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"),
)
_TENS = ("thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred")
_NUMBERS = {word: n for n, word in enumerate(_UNITS, start=2)} | {
    word: 10 * n for n, word in enumerate(_TENS, start=3)
}
_NUMBER = r"(?:[0-9]+|" + "|".join(_NUMBERS) + r")\b"
# A number after the word makes a product, as in "365 times 24", rather than a count of copies.
_COUNT = re.compile(rf"\b({_NUMBER})\s+(?:times|copies)\b(?!\s*{_NUMBER})")


def _words(text: str) -> str:
    return " " + " ".join(_WORD.findall(text.lower())) + " "


def _asked_count(query: str) -> int:
    counts = [_NUMBERS.get(n) or int(n) for n in _COUNT.findall(query.lower())]
    return max(counts, default=0)


class RepeatWatch:
    """Reads one reply as it streams and reports when one block of lines comes back to back."""

    def __init__(self, query: str) -> None:
        self._query = _words(query)
        uncounted = any(phrase in self._query for phrase in _UNCOUNTED)
        self._copies = max(_COPIES, _asked_count(query) + 1, _UNCOUNTED_COPIES if uncounted else 0)
        self._partial = ""
        self._recent: deque[str] = deque(maxlen=_LONGEST_BLOCK + 1)
        self._runs = [0] * _LONGEST_BLOCK

    def feed(self, text: str) -> bool:
        """Take the next piece of reply text and return whether the reply now repeats."""
        *complete, self._partial = (self._partial + text).split("\n")
        for line in complete:
            key = line.strip()
            if key and self._add(key):
                return True
        return False

    def _add(self, key: str) -> bool:
        self._recent.append(key)
        sizes = range(1, _LONGEST_BLOCK + 1)
        for size in sizes:
            same = len(self._recent) > size and self._recent[-1 - size] == key
            self._runs[size - 1] = self._runs[size - 1] + 1 if same else 0
        return any(self._repeats(size) for size in sizes)

    def _repeats(self, size: int) -> bool:
        if self._runs[size - 1] < size * (self._copies - 1):
            return False
        return any(map(self._counted, list(self._recent)[-size:]))

    def _counted(self, line: str) -> bool:
        if len(line) < _MIN_LINE_CHARS or _LETTER.search(line) is None:
            return False
        return _words(line) not in self._query
