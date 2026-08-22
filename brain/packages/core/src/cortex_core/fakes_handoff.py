"""In-memory ``HandoffStore``, tested against the same contract as the Redis adapter."""

from dataclasses import replace

from cortex_core.handoff import HandoffRecord, HandoffState


class InMemoryHandoffStore:
    """HandoffStore held in a dict plus the single active-handoff pointer, for tests and CI."""

    def __init__(self) -> None:
        self._records: dict[str, HandoffRecord] = {}
        self._active_id: str | None = None

    async def put(self, record: HandoffRecord) -> None:
        """Persist one record; a non-terminal one becomes the active handoff."""
        self._records[record.handoff_id] = record
        if not record.state.terminal:
            self._active_id = record.handoff_id
        elif self._active_id == record.handoff_id:
            self._active_id = None

    async def get(self, handoff_id: str) -> HandoffRecord | None:
        """Return the record with ``handoff_id``, or None when unknown."""
        return self._records.get(handoff_id)

    async def transition(
        self, handoff_id: str, state: HandoffState, *, failure: str | None = None
    ) -> bool:
        """Rewrite the record's state and reason (False for an unknown id, never an error)."""
        record = self._records.get(handoff_id)
        if record is None:
            return False
        await self.put(replace(record, state=state, failure=failure))
        return True

    async def delete(self, handoff_id: str) -> None:
        """Remove the record, idempotently, clearing the active pointer when it points here."""
        self._records.pop(handoff_id, None)
        if self._active_id == handoff_id:
            self._active_id = None

    async def active(self) -> HandoffRecord | None:
        """Return the one in-flight (non-terminal) record, or None when no handoff is live."""
        if self._active_id is None:
            return None
        return self._records[self._active_id]
