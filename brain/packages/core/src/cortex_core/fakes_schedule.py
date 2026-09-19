"""In-memory ``ScheduleStore``, tested against the same contract as the Redis adapter."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import uuid4

from cortex_core.schedule import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleStatus,
)
from cortex_core.schedule_transitions import ScheduleEdit, acks_fire, apply_edit, apply_snooze


def _uuid4_token() -> str:
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class _LiveClaim:
    """The store's private view of one FIRING item: its fencing token and claim time."""

    token: str
    at: datetime


class InMemoryScheduleStore:
    """ScheduleStore kept in dicts; ``token_factory`` is injected so a test can fix the tokens."""

    def __init__(self, *, token_factory: Callable[[], str] = _uuid4_token) -> None:
        self._items: dict[str, ScheduledItem] = {}
        self._claims: dict[str, _LiveClaim] = {}
        self._token_factory = token_factory

    async def add(self, item: ScheduledItem) -> None:
        """Persist one schedule (PENDING; overwrites an item with the same id)."""
        self._items[item.id] = item

    async def get(self, item_id: str) -> ScheduledItem | None:
        """Return the item with ``item_id``, or None when unknown."""
        return self._items.get(item_id)

    async def list_active(self) -> Sequence[ScheduledItem]:
        """PENDING/FIRING items plus fired-but-undelivered ones, due order."""
        return tuple(sorted(self._items.values(), key=lambda item: item.due_at))

    async def cancel(self, item_id: str) -> bool:
        """Delete the item outright, whether pending, firing, or fired-but-undelivered."""
        self._claims.pop(item_id, None)
        return self._items.pop(item_id, None) is not None

    async def snooze(self, item_id: str, *, until: datetime) -> bool:
        """Postpone an item to ``until`` via ``apply_snooze``; FIRING and unknown answer False."""
        item = self._items.get(item_id)
        if item is None or item.status is ScheduleStatus.FIRING:
            return False
        self._items[item_id] = apply_snooze(item, until)
        return True

    async def edit(self, item_id: str, edit: ScheduleEdit) -> bool:
        """Retext / re-recur a non-FIRING item via ``apply_edit``; FIRING/unknown answer False."""
        item = self._items.get(item_id)
        if item is None or item.status is ScheduleStatus.FIRING:
            return False
        self._items[item_id] = apply_edit(item, edit)
        return True

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]:
        """Claim due PENDING items and lease-expired FIRING ones, oldest-due-first."""
        eligible = [
            item
            for item in self._items.values()
            if (item.status is ScheduleStatus.PENDING and item.due_at <= now)
            or (item.status is ScheduleStatus.FIRING and self._claims[item.id].at + lease <= now)
        ]
        eligible.sort(key=lambda item: item.due_at)
        claims: list[ScheduleClaim] = []
        for item in eligible[:limit]:
            firing = replace(item, status=ScheduleStatus.FIRING)
            token = self._token_factory()
            self._items[item.id] = firing
            self._claims[item.id] = _LiveClaim(token=token, at=now)
            claims.append(ScheduleClaim(item=firing, token=token))
        return tuple(claims)

    def _holds(self, claim: ScheduleClaim) -> bool:
        """Whether ``claim`` is the item's current claim (present, FIRING, token match)."""
        item = self._items.get(claim.item.id)
        live = self._claims.get(claim.item.id)
        if item is None or live is None or item.status is not ScheduleStatus.FIRING:
            return False
        return live.token == claim.token

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
        """Persist one fire under the claim's token; a stale claimant no-ops False."""
        if not self._holds(claim):
            return False
        item = self._items[claim.item.id]
        del self._claims[claim.item.id]
        tainted = item.tainted or outcome.tainted
        deliverable_since = outcome.fired_at if outcome.deliverable else item.deliverable_since
        if outcome.next_due is not None:
            self._items[claim.item.id] = replace(
                item,
                status=ScheduleStatus.PENDING,
                due_at=outcome.next_due,
                tainted=tainted,
                deliverable_since=deliverable_since,
                last_outcome=outcome.outcome,
            )
        elif deliverable_since is not None:
            self._items[claim.item.id] = replace(
                item,
                status=ScheduleStatus.DONE,
                tainted=tainted,
                deliverable_since=deliverable_since,
                last_outcome=outcome.outcome,
            )
        else:
            del self._items[claim.item.id]
        return True

    async def release(self, claim: ScheduleClaim) -> bool:
        """Un-claim (FIRING → PENDING, due unchanged) under the token; stale no-ops False."""
        if not self._holds(claim):
            return False
        item = self._items[claim.item.id]
        del self._claims[claim.item.id]
        self._items[claim.item.id] = replace(item, status=ScheduleStatus.PENDING)
        return True

    async def deliverable(self) -> Sequence[ScheduledItem]:
        """Fired reminders awaiting ack, oldest-fired-first."""
        due = [item for item in self._items.values() if item.deliverable_since is not None]
        due.sort(key=lambda item: item.deliverable_since or item.due_at)
        return tuple(due)

    async def ack(self, item_id: str, *, fired_at: datetime | None) -> bool:
        """Clear the fire ``fired_at`` names; a DONE one-shot is deleted."""
        item = self._items.get(item_id)
        if item is None or not acks_fire(item, fired_at):
            return False
        if item.status is ScheduleStatus.DONE:
            del self._items[item_id]
        else:
            self._items[item_id] = replace(item, deliverable_since=None)
        return True
