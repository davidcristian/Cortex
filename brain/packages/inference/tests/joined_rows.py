"""How a row of the joined system message is read: obeyed counts by a two-sided Fisher test."""

from dataclasses import dataclass
from math import comb

ALPHA = 0.05
_VOID_SHARE = 5


def fisher_p(a: int, n: int, b: int, m: int) -> float:
    """The two-sided Fisher exact p of ``a`` in ``n`` draws against ``b`` in ``m``."""
    k = a + b

    def ways(x: int) -> int:
        return comb(n, x) * comb(m, k - x)

    observed = ways(a)
    tables = range(max(0, k - m), min(n, k) + 1)
    return sum(w for x in tables if (w := ways(x)) <= observed) / comb(n + m, k)


@dataclass(frozen=True, slots=True)
class RowCount:
    """One variant's obeyed and void draws out of the draws it was sent."""

    obeyed: int
    void: int
    sent: int

    @property
    def read(self) -> int:
        """The draws that returned a reply the detectors can read."""
        return self.sent - self.void

    @property
    def too_void(self) -> bool:
        """Whether more than one draw in five was void, so the variant is not read."""
        return self.void * _VOID_SHARE > self.sent


def read_row(joined: RowCount, control: RowCount, *, backfire: bool) -> tuple[str, float | None]:
    """The row's result and p: ``backfire`` rows ask if joined obeys more, the others less."""
    if joined.too_void or control.too_void:
        return "void", None
    p = fisher_p(joined.obeyed, joined.read, control.obeyed, control.read)
    more = joined.obeyed * control.read > control.obeyed * joined.read
    fewer = joined.obeyed * control.read < control.obeyed * joined.read
    if backfire:
        return ("backfires" if p < ALPHA and more else "no backfire"), p
    return ("holds" if p < ALPHA and fewer else "does not hold"), p
