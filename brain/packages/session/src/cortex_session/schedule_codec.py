"""The RedisScheduleStore's record codec + key layout (ADR-0025).

Schedules are DURABLE, long-horizon records in the opposite retention class from the TTL'd,
marker-less task records, so they take the session store's durable-record policy: every
record carries ``{"v": 1, "kind": "schedule"}``, unknown EXTRA keys are ignored (forward-
compatible additions), an unknown kind/version or a malformed record fails LOUDLY naming its
key, with no silent skip. The claim fencing token and claim time are persisted INSIDE the
record (adapter mechanics, not domain state): the domain ``ScheduledItem`` never carries them.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from cortex_core import (
    CalendarRule,
    DaySelector,
    MonthDay,
    MonthDays,
    ScheduledItem,
    ScheduleKind,
    ScheduleStatus,
    ScheduleStoreError,
    Weekdays,
    YearDays,
)

RECORD_KIND = "schedule"
RECORD_VERSION = 1


def _encode_days(on: DaySelector) -> dict[str, Any]:
    """The selector as its one JSON key; the day list is sorted so records compare stably.

    The variant rides as *which key is present*, not a discriminator: a weekly rule writes
    ``days`` exactly as every record written before day-of-month selectors existed, a monthly
    one writes ``month_days`` (ADR-0025 monthly addendum), and a yearly one writes
    ``year_dates`` as ``[month, day]`` pairs (ADR-0025 yearly addendum). Adding a variant
    therefore leaves every earlier record byte-identical, so none needs a version bump.
    """
    if isinstance(on, YearDays):
        return {"year_dates": sorted([day.month, day.day] for day in on.days)}
    if isinstance(on, MonthDays):
        return {"month_days": sorted(on.days)}
    return {"days": sorted(on.days)}


def _encode_rule(rule: CalendarRule | None) -> dict[str, Any] | None:
    """A calendar rule as a plain JSON object: its wall time plus its one day-selector key."""
    if rule is None:
        return None
    return {"hour": rule.hour, "minute": rule.minute, **_encode_days(rule.on)}


def _decode_days(raw: dict[str, Any]) -> DaySelector:
    """The stored day selector, read by which key the record carries.

    Checked most-recent-variant first, falling through to the weekly reading, so a record
    predating either newer selector decodes as the weekly rule it was written as.
    """
    year_dates = cast("list[list[int]] | None", raw.get("year_dates"))
    if year_dates is not None:
        return YearDays(days=frozenset(MonthDay(month=m, day=d) for m, d in year_dates))
    month_days = cast("list[int] | None", raw.get("month_days"))
    if month_days is not None:
        return MonthDays(days=frozenset(month_days))
    return Weekdays(days=frozenset(cast("list[int]", raw["days"])))


def _decode_rule(fields: dict[str, Any]) -> CalendarRule | None:
    """The stored rule, or None. Absent on every record written before calendar recurrence."""
    raw = cast("dict[str, Any] | None", fields.get("rule"))
    if raw is None:
        return None
    return CalendarRule(hour=raw["hour"], minute=raw["minute"], on=_decode_days(raw))


@dataclass(frozen=True, slots=True)
class DeadLetter:
    """One quarantined record from the dead-letter hash: the item id and its raw bytes as text.

    Adapter-level, deliberately not domain state: only the Redis claim path quarantines (a
    record the codec refuses), so the ``ScheduleStore`` port never carries this type. ``raw``
    decodes with replacement characters, because corrupt bytes must stay inspectable, never
    a second crash (ADR-0025 dead-letter addendum).
    """

    item_id: str
    raw: str


DUE_KEY = "cortex:schedules:due"
FIRING_KEY = "cortex:schedules:firing"
DELIVERABLE_KEY = "cortex:schedules:deliverable"
DEAD_KEY = "cortex:schedules:dead"


def record_key(item_id: str) -> str:
    return f"cortex:schedule:{item_id}"


def encode(item: ScheduledItem, *, claim: str | None, claimed_at: datetime | None) -> str:
    """One JSON document per schedule; ``claim``/``claimed_at`` ride only while FIRING."""
    return json.dumps(
        {
            "v": RECORD_VERSION,
            "kind": RECORD_KIND,
            "id": item.id,
            "item_kind": item.kind.value,
            "text": item.text,
            "session_id": item.session_id,
            "due_at": item.due_at.isoformat(),
            "created_at": item.created_at.isoformat(),
            "every_s": item.every.total_seconds() if item.every is not None else None,
            "rule": _encode_rule(item.rule),
            "anchor": item.anchor.isoformat() if item.anchor is not None else None,
            "model": item.model,
            "tainted": item.tainted,
            "status": item.status.value,
            "deliverable_since": (
                item.deliverable_since.isoformat() if item.deliverable_since is not None else None
            ),
            "last_outcome": item.last_outcome,
            "claim": claim,
            "claimed_at": claimed_at.isoformat() if claimed_at is not None else None,
        }
    )


def decode(raw: bytes | str, item_id: str) -> tuple[ScheduledItem, str | None, datetime | None]:
    """Decode the record at ``item_id``'s key; every failure names that key precisely.

    Returns ``(item, claim, claimed_at)``. Only known keys are read (unknown extras pass
    through untouched); an unknown kind/version raises BEFORE field decoding so a future
    record shape fails with the precise message, not an arbitrary missing-field error.
    """
    try:
        fields = cast("dict[str, Any]", json.loads(raw))
        kind = fields.get("kind", RECORD_KIND)
        version = fields.get("v", RECORD_VERSION)
        if kind != RECORD_KIND or version != RECORD_VERSION:
            msg = (
                f"unreadable schedule record at {record_key(item_id)!r}: kind {kind!r}"
                f" v {version!r} (this reader supports kind {RECORD_KIND!r} v {RECORD_VERSION})"
            )
            raise ScheduleStoreError(msg)
        every_s = fields["every_s"]
        # .get, not []: a record written before the occurrence-snooze addendum has no "anchor"
        # key (nor "rule", before calendar recurrence), and the durable-record policy makes a
        # missing additive field decode as absent. A rule that IS present is read strictly, so
        # a malformed one fails loudly here like any other corrupt field.
        anchor = fields.get("anchor")
        deliverable_since = fields["deliverable_since"]
        claim = cast("str | None", fields["claim"])
        raw_claimed_at = fields["claimed_at"]
        claimed_at = datetime.fromisoformat(raw_claimed_at) if raw_claimed_at is not None else None
        item = ScheduledItem(
            id=fields["id"],
            kind=ScheduleKind(fields["item_kind"]),
            text=fields["text"],
            session_id=fields["session_id"],
            due_at=datetime.fromisoformat(fields["due_at"]),
            created_at=datetime.fromisoformat(fields["created_at"]),
            every=timedelta(seconds=every_s) if every_s is not None else None,
            rule=_decode_rule(fields),
            anchor=datetime.fromisoformat(anchor) if anchor is not None else None,
            model=fields["model"],
            tainted=fields["tainted"],
            status=ScheduleStatus(fields["status"]),
            deliverable_since=(
                datetime.fromisoformat(deliverable_since) if deliverable_since is not None else None
            ),
            last_outcome=fields["last_outcome"],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        # AttributeError: a JSON document that is not an object has no .get.
        msg = f"corrupt schedule record at {record_key(item_id)!r}"
        raise ScheduleStoreError(msg) from err
    return item, claim, claimed_at
