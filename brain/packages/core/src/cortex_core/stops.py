"""Collecting what a loop's completions said about why they ended."""

from cortex_core.inference import DecodeStop, StopReason

__all__ = ["StopLedger"]


class StopLedger:
    """Collects why each completion of one loop ended, and answers whether one was cut."""

    def __init__(self) -> None:
        self._capped = False

    def observe(self, stop: DecodeStop) -> None:
        """Take one completion's reported reason for ending."""
        if stop.reason is StopReason.CAPPED:
            self._capped = True

    @property
    def capped(self) -> bool:
        """Whether any completion this ledger saw stopped at a token limit."""
        return self._capped
