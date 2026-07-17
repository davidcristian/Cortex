"""In-memory ``HandoffStore`` fake: the contract twin of the Redis adapter (ADR-0030).

Split out of ``fakes.py`` for the line cap (the ``fakes_body``/``fakes_schedule``/
``fakes_session`` precedent). Like the other in-memory fakes it does NOT survive a process
restart; the Redis adapter is what proves a handoff record outlives the swap, and this twin
only has to be observably interchangeable with it behind the ``HandoffStore`` port.
"""

from dataclasses import replace

from cortex_core.handoff import HandoffRecord, HandoffState


class InMemoryHandoffStore:
    """HandoffStore held in a dict plus the single active-handoff pointer, for tests and CI.

    The pointer mirrors the Redis adapter's active key: ``put`` of a non-terminal record
    claims it (at most one handoff is in flight, so the last non-terminal put wins; the
    conductor checks ``active()`` before snapshotting), a terminal ``put`` or ``transition``
    releases it, and ``delete`` clears it when it names the deleted record. Terminal records
    stay readable via ``get`` (the fake has no TTL to expire them) but are never ``active``.
    """

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

    async def transition(self, handoff_id: str, state: HandoffState) -> bool:
        """Rewrite the record's state (False for an unknown id, never an error)."""
        record = self._records.get(handoff_id)
        if record is None:
            return False
        await self.put(replace(record, state=state))
        return True

    async def delete(self, handoff_id: str) -> None:
        """Remove the record outright, idempotently, releasing the pointer if it names it."""
        self._records.pop(handoff_id, None)
        if self._active_id == handoff_id:
            self._active_id = None

    async def active(self) -> HandoffRecord | None:
        """Return the one in-flight (non-terminal) record, or None when no handoff is live."""
        if self._active_id is None:
            return None
        return self._records[self._active_id]
