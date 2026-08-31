"""Collecting what a loop's completions said about why they ended (ADR-0005 finish-reason
addendum).

Pure policy over the ``DecodeStop`` events a backend reports, with no I/O and no logging of its
own. The loop hands each completion's report here, and the ledger answers one question: did
anything this loop decoded stop at a token limit rather than at an end of its own. A delegated
attempt whose reply was cut is an attempt that did not answer, whatever the fragment reads like.
``docs/modules/brain-core.md`` records the two properties behind the answer, that an absent
report is not a cap and that any completion counts rather than the last.
"""

from cortex_core.inference import DecodeStop, StopReason

__all__ = ["StopLedger"]


class StopLedger:
    """Collects why each completion of one loop ended, and answers whether one was cut.

    One ledger per attempt rather than per completion, because the caller's question spans the
    whole loop. It is stateful and deliberately not stored anywhere (the one hard rule): a ledger
    is scratch for the duration of one run, and its conclusion is reported as an outcome.
    """

    def __init__(self) -> None:
        self._capped = False

    def observe(self, stop: DecodeStop) -> None:
        """Take one completion's reported reason for ending."""
        if stop.reason is StopReason.CAPPED:
            self._capped = True

    @property
    def capped(self) -> bool:
        """Whether any completion this ledger saw stopped at a token limit.

        False both for a loop whose completions all ended themselves and for one whose backend
        reported nothing. Conflating those two is safe here because the caller acts only on True,
        so a quiet backend is treated exactly as it was before this ledger existed. A caller that
        needs the distinction reads the port's own events, where an absent report and ``FINISHED``
        stay apart.
        """
        return self._capped
