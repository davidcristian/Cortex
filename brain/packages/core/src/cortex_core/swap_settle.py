"""Settling a handoff record, and the store claim each write does or does not release."""

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
        """Move the record to ``state``, and free the store's claim once it is settled."""
        await self._settle(record, state, None)

    async def fail(self, record: HandoffRecord, reason: str) -> None:
        """Settle the record ``FAILED``, saying why, in the log and on the record alike."""
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
        # The store's active pointer is released only by a settling write or a delete, so a
        # terminal state it refused is followed by deleting the record: a finished handoff left
        # holding the pointer would refuse every later escalation until the next restart.
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
            _logger.exception(
                "could not release the finished handoff; escalation stays refused until a restart",
                extra={"session_id": record.session_id, "turn_id": record.handoff_id},
            )
