# The weekday note holds one item of several a day off

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-09

`weekday_off_after` in `schedule_weekday.py` holds one item id and date. When a turn stores two
one-time items a day off the named weekday, the pair names the later one, and a cancel or move of
that item drops the note while the earlier item is still a day off
([readings](../../readings/schedule-one-time-weekday.md#audit-probes-of-the-held-item-2026-11-09)).

## What to do

1. Hold every item a day off, by id, and drop only the one a later call changes.
2. Test two stores a day off, then a cancel of the later one: the note still names the earlier.

## History

- 2026-11-09: filed from the audit probes of the held item.
