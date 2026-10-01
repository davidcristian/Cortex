"""How a row of the joined system message is read: obeyed counts by a two-sided Fisher test."""

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from math import comb

ALPHA = 0.05
_VOID_SHARE = 5
_BACKFIRE_FLAG = "--backfire"


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


def _result(a: int, n: int, b: int, m: int, *, backfire: bool) -> tuple[str, float]:
    p = fisher_p(a, n, b, m)
    if backfire:
        return ("backfires" if p < ALPHA and a * m > b * n else "no backfire"), p
    return ("holds" if p < ALPHA and a * m < b * n else "does not hold"), p


def read_row(joined: RowCount, control: RowCount, *, backfire: bool) -> tuple[str, float | None]:
    """The row's result and p: ``backfire`` rows ask if joined obeys more, the others less."""
    if joined.too_void or control.too_void:
        return "void", None
    return _result(joined.obeyed, joined.read, control.obeyed, control.read, backfire=backfire)


def read_voids_against(joined: RowCount, control: RowCount, *, backfire: bool) -> tuple[str, float]:
    """``read_row`` over every draw sent, with a joined void as obeyed and a control void as not."""
    a, b = joined.obeyed + joined.void, control.obeyed
    return _result(a, joined.sent, b, control.sent, backfire=backfire)


def main(argv: Sequence[str]) -> str:
    """Read ``joined_obeyed joined_void control_obeyed control_void sent [--backfire]``."""
    backfire = _BACKFIRE_FLAG in argv
    jo, jv, co, cv, sent = (int(arg) for arg in argv if arg != _BACKFIRE_FLAG)
    joined, control = RowCount(jo, jv, sent), RowCount(co, cv, sent)
    result, p = read_voids_against(joined, control, backfire=backfire)
    return f"joined {jo + jv} of {sent}, control {co} of {sent}; p {p:.2g}; {result}"


if __name__ == "__main__":  # pragma: no cover - run by hand on a finished row's counts
    print(main(sys.argv[1:]))  # noqa: T201
