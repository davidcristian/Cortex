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
        written = await self._write_state(record.handoff_id, state)
        if state is HandoffState.DONE or (state.terminal and not written):
            await self._release_claim(record.handoff_id)

    async def _write_state(self, handoff_id: str, state: HandoffState) -> bool:
        """Write one state onto the record; False when the store refused it."""
        try:
            await self._handoffs.transition(handoff_id, state)
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
