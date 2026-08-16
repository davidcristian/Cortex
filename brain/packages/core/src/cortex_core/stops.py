"""Collecting what a loop's completions said about why they ended (ADR-0005 finish-reason
addendum).

Pure policy over the ``DecodeStop`` events a backend reports, with no I/O and no logging of its
own, and the twin of ``CadenceWatch`` on the other closing event: the loop hands each completion's
report here, and the caller that owns the ledger decides what to say about it. It answers one
question, "did anything this loop decoded stop at a token limit rather than at an end of its own",
because that is the question its consumer asks. A delegated attempt whose reply was cut is an
attempt that did not answer, whatever the fragment reads like.

Two properties keep the answer honest, and both exist because the alternative is a lie in the
direction that costs the reader:

- **Silence is not a cap.** A backend whose engine reports no reason at all leaves this ledger
  saying exactly what it said before anything ran, which is the behaviour this repo shipped when
  nothing could ask. Manufacturing a cap out of an absent report would fail every completion of
  every build that stays quiet.
- **Any completion counts, not the last.** A tool loop decodes several times under one attempt,
  and the material a cut round dropped is missing from the answer whether or not the round after
  it ended cleanly. So the ledger folds by "was one of them capped" rather than by "how did this
  one end".
"""

from cortex_core.inference import DecodeStop, StopReason

__all__ = ["StopLedger"]


class StopLedger:
    """Collects why each completion of one loop ended, and answers whether one was cut.

    One ledger per attempt, not per completion, for the reason a ``CadenceWatch`` is one per
    handoff: the caller's question spans the whole loop. Stateful by design and deliberately not
    stored anywhere (the one hard rule): a ledger is scratch for the duration of one run, and its
    conclusion is reported as an outcome rather than kept.
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
        reported nothing, and those two are not the same fact; what makes conflating them safe
        here is that the caller acts only on True, so a quiet backend is treated exactly as it was
        before this ledger existed. A caller that ever needs the distinction reads the port's own
        events, where silence and ``FINISHED`` stay apart.
        """
        return self._capped
