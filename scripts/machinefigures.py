"""Find figures in watts or a clock unit, which describe only the machine they were read on."""

import bisect
import itertools
import re
from collections.abc import Sequence

import bannedwords
from bannedwords import Hit, Line

_NUMBER = r"(?<![\w.])\d+(?:[.,]\d+)*"
_CLOCK = r"(?i:[mg]hz)(?!\w)"
_FIGURE = re.compile(
    rf"{_NUMBER}\s*(?:{_CLOCK}|(?:k?W|(?i:watts?))(?!\w))|(?<!\w){_CLOCK}",
)


def find_figures(run: Sequence[Line]) -> list[Hit]:
    """Return every such figure in one run of consecutive lines, on the line where it starts.

    A clock unit is found without a number too, as a table header writes it.
    """
    masked = bannedwords.mask("\n".join(text for _, text in run))
    starts = list(itertools.accumulate((len(text) + 1 for _, text in run), initial=0))
    return [
        Hit(
            line=run[bisect.bisect_right(starts, found.start()) - 1][0],
            word=" ".join(found.group().split()),
        )
        for found in _FIGURE.finditer(masked)
    ]
