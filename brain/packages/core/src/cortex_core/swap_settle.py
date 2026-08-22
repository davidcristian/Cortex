"""Settling a handoff record, and the store claim each write does or does not release (ADR-0030).

Split from ``swap_conductor.py`` along the seam the ADR's own addendum named: settling a handoff
and releasing its claim are two different writes, and which of them is owed depends on the state
being written rather than on where in the sequence the write happens. The conductor owns the
order the machine changes hands in; this owns what the record owes at each of those moments.

The rule in one sentence: the store's active pointer is held by whichever non-terminal record was
last written, and only a settling write or a delete gives it back, so a terminal state the store
refused is followed by dropping the record rather than by keeping a diagnosis copy that would
wedge every later escalation. Nothing here raises: a store that fails while a converged swap is
being written down must not turn that swap into a crash.

Settling **failed** is its own verb, and that is the whole of the failed-reason addendum: a
handoff that failed owes a reason, so ``fail`` takes one where ``advance`` cannot, and no caller
can write the state without it. The reason goes to two places at once, which is deliberate,
because each covers the other's failure. It goes onto the record, where it outlives this process
and is the only thing a later reader of a ``FAILED`` record has. It goes into one line of this
brain's own log, where an operator correlating a failure while a user waits will actually look,
and where it still lands when the store is the thing that broke and the record cannot carry it.
"""

import logging

from cortex_core.errors import HandoffStoreError
from cortex_core.handoff import HandoffRecord, HandoffState
from cortex_core.ports import HandoffStore

_logger = logging.getLogger(__name__)


class HandoffSettler:
    """Writes one handoff record's states, and frees the store's claim once it is settled."""

    def __init__(self, handoffs: HandoffStore) -> None:
        self._handoffs = handoffs

    async def advance(self, record: HandoffRecord, state: HandoffState) -> None:
        """Move the record to ``state``, and free the store's claim once it is settled.

        Every state but ``FAILED``, which owes a reason and goes through ``fail`` below. What
        this leaves is the two writes that need none: a handoff reaching the deep model, and one
        finishing.

        Never raises: a store that fails here must not turn a converged swap into a crash. But
        the release is **not** conditional on the write landing, and that is the point. The
        store's active pointer is held by whichever non-terminal record was last written, and
        only the settling write or a delete releases it. A settle that failed would therefore
        leave a finished handoff holding the pointer, and ``active()`` would refuse every later
        escalation in this process with a note saying a handoff is in flight when none is, until
        the next restart. So a terminal state that could not be written is followed by deleting
        the record instead: a diagnosis copy the store refused to update is worth less than the
        escalation path it would otherwise wedge, and the same failure is logged loudly with the
        handoff's id either way. A failed **intermediate** write keeps the record, because the
        handoff really is still live there and boot recovery is what settles it.
        """
        await self._settle(record.handoff_id, state, None)

    async def fail(self, record: HandoffRecord, reason: str) -> None:
        """Settle the record ``FAILED``, saying why, in the log and on the record alike.

        A separate verb rather than a defaulted argument, so that no path can settle a handoff
        failed without saying what happened: the reason is the thing the swap in used to lose
        (ADR-0030 failed-reason addendum), and an optional one would have gone missing exactly
        where it went missing before. ``reason`` is app-authored (``swap_reasons.py``) or the
        message of the error that ended the sequence, which on the swap path carries the model
        host's own sentence.

        The line is written before the store is asked, and unconditionally, because the store is
        one of the things that can be broken here: a record that could not be updated cannot
        carry its own reason, and that is the moment the log is the only copy. It is a WARNING
        rather than an error, and the level is a statement about the machine rather than about
        the disappointment: every path that reaches here has converged back to a serving cortex
        and told the user so. The levels that mean somebody must act are already spent on the
        failures where somebody must, a cortex that would not come back among them.
        """
        _logger.warning(
            "a handoff ended failed",
            extra={"handoff": record.handoff_id, "reason": reason},
        )
        await self._settle(record.handoff_id, HandoffState.FAILED, reason)

    async def _settle(self, handoff_id: str, state: HandoffState, failure: str | None) -> None:
        """Write one state, then release the claim if this write is what owed it."""
        written = await self._write_state(handoff_id, state, failure)
        if state is HandoffState.DONE or (state.terminal and not written):
            await self._release_claim(handoff_id)

    async def _write_state(self, handoff_id: str, state: HandoffState, failure: str | None) -> bool:
        """Write one state onto the record; False when the store refused it."""
        try:
            await self._handoffs.transition(handoff_id, state, failure=failure)
        except HandoffStoreError:
            _logger.exception(
                "could not record the handoff's state",
                extra={"handoff": handoff_id, "state": state.value},
            )
            return False
        return True

    async def _release_claim(self, handoff_id: str) -> None:
        """Delete the finished record, so nothing later reads it as a handoff in flight."""
        try:
            await self._handoffs.delete(handoff_id)
        except HandoffStoreError:
            # Nothing else this process can do: the record stays live until boot recovery, and
            # escalation stays refused until then, which is the failure the log has to name.
            _logger.exception(
                "could not release the finished handoff; escalation stays refused until a restart",
                extra={"handoff": handoff_id},
            )
