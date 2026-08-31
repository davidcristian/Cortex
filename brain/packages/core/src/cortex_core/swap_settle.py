"""Settling a handoff record, and the store claim each write does or does not release (ADR-0030).

Split from ``swap_conductor.py`` along the seam the ADR's own addendum named: settling a handoff
and releasing its claim are two different writes, and which of them is owed depends on the state
being written rather than on where in the sequence the write happens. The conductor owns the order
the machine changes hands in; this module owns what the record owes at each of those moments.

The store's active pointer is held by whichever non-terminal record was last written, and only a
settling write or a delete gives it back, so a terminal state the store rejected is followed by
dropping the record rather than by keeping a diagnosis copy that would wedge every later
escalation. Nothing here raises: a store that fails while a converged swap is being written down
must not turn that swap into a crash.

``fail`` is a separate verb from ``advance`` because a handoff that failed owes a reason, and an
optional argument would go missing where it went missing before (ADR-0030 failed-reason addendum).
The reason goes to two places, each covering the other's failure: onto the record, where it
outlives this process and is all a later reader of a ``FAILED`` record has, and into one line of
this brain's own log, which still lands when the store is the thing that broke.

Every line here names its work ``turn_id`` and not ``handoff``, a handoff id being the escalating
turn's id (``handoff.py``), so one grep by turn reaches the settle, the turn's own failures and
every tool call it made (ADR-0009 sixth-name addendum). The record's field keeps its own name,
being a wire format that outlives the deployment. All three lines also name the conversation
(ADR-0009 named-conversation addendum), which is why the private writes below take the record
rather than a bare id: the three are one account of settling one handoff, so a reader grepping the
chat must reach the failure, the state that could not be written and the record that could not be
released alike, rather than only the first of the three.
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

        Every state but ``FAILED``, which owes a reason and goes through ``fail`` below, leaving
        the two writes that need none: a handoff reaching the deep model, and one finishing.

        Never raises, and the release is deliberately not conditional on the write landing. The
        store's active pointer is held by whichever non-terminal record was last written, and only
        the settling write or a delete releases it, so a settle that failed would leave a finished
        handoff holding the pointer and ``active()`` would reject every later escalation in this
        process, with a note saying a handoff is in flight when none is, until the next restart. A
        terminal state that could not be written is therefore followed by deleting the record: a
        diagnosis copy the store would not update is worth less than the escalation path it would
        wedge, and the failure is logged with the handoff's id either way. A failed intermediate
        write keeps the record, because the handoff really is still live there and boot recovery is
        what settles it.
        """
        await self._settle(record, state, None)

    async def fail(self, record: HandoffRecord, reason: str) -> None:
        """Settle the record ``FAILED``, saying why, in the log and on the record alike.

        ``reason`` is app-authored (``swap_reasons.py``) or the message of the error that ended the
        sequence, which on the swap path carries the model host's own message.

        The line is written before the store is asked, and unconditionally, because the store is
        one of the things that can be broken here: a record that could not be updated cannot carry
        its own reason, and the log is then the only copy. The level is WARNING rather than ERROR
        because every path that reaches here has converged back to a serving cortex and said so on
        the turn's stream. The louder levels are spent on the failures somebody must act on, a
        cortex that would not come back among them.
        """
        _logger.warning(
            "a handoff ended failed",
            extra={
                "session_id": record.session_id,
                "turn_id": record.handoff_id,
                "reason": reason,
            },
        )
        await self._settle(record, HandoffState.FAILED, reason)

    async def _settle(
        self, record: HandoffRecord, state: HandoffState, failure: str | None
    ) -> None:
        """Write one state, then release the claim if this write is what owed it."""
        written = await self._write_state(record, state, failure)
        if state is HandoffState.DONE or (state.terminal and not written):
            await self._release_claim(record)

    async def _write_state(
        self, record: HandoffRecord, state: HandoffState, failure: str | None
    ) -> bool:
        """Write one state onto the record; False when the store refused it."""
        try:
            await self._handoffs.transition(record.handoff_id, state, failure=failure)
        except HandoffStoreError:
            _logger.exception(
                "could not record the handoff's state",
                extra={
                    "session_id": record.session_id,
                    "turn_id": record.handoff_id,
                    "state": state.value,
                },
            )
            return False
        return True

    async def _release_claim(self, record: HandoffRecord) -> None:
        """Delete the finished record, so nothing later reads it as a handoff in flight."""
        try:
            await self._handoffs.delete(record.handoff_id)
        except HandoffStoreError:
            # Nothing else this process can do: the record stays live until boot recovery, and
            # escalation stays refused until then, which is the failure the log has to name.
            _logger.exception(
                "could not release the finished handoff; escalation stays refused until a restart",
                extra={"session_id": record.session_id, "turn_id": record.handoff_id},
            )
