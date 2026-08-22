"""Settling a handoff record, and the store claim each write does or does not release (ADR-0030)."""

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
        await self._settle(record.handoff_id, state, None)

    async def fail(self, record: HandoffRecord, reason: str) -> None:
        """Settle the record ``FAILED``, saying why, in the log and on the record alike."""
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
