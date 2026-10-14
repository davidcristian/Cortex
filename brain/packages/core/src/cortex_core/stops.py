"""Collecting what a loop's completions said about why they ended."""

from cortex_core.inference import DecodeStop, StopReason

__all__ = ["StopLedger"]


class StopLedger:
    """Collects why one loop and each of its completions ended, for the notes a turn ends with."""

    def __init__(self) -> None:
        self._capped = False
        self._out_of_rounds = False
        self._repeated = False

    def observe(self, stop: DecodeStop) -> None:
        """Take one completion's reported reason for ending."""
        if stop.reason is StopReason.CAPPED:
            self._capped = True

    def observe_round_limit(self) -> None:
        """Take the loop's report that its last allowed round still ended in tool calls."""
        self._out_of_rounds = True

    def observe_repeat(self) -> None:
        """Take the turn's report that it ended a reply that repeated one line."""
        self._repeated = True

    @property
    def capped(self) -> bool:
        """Whether any completion this ledger saw stopped at a token limit."""
        return self._capped

    @property
    def out_of_rounds(self) -> bool:
        """Whether the loop stopped at its round limit instead of at a reply."""
        return self._out_of_rounds

    @property
    def repeated(self) -> bool:
        """Whether the turn ended a reply early because it repeated one line."""
        return self._repeated
