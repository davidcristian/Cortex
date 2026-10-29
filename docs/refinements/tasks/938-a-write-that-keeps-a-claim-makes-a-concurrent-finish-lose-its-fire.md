# A write that keeps a claim makes a concurrent finish lose its fire

**Status:** done 2026-10-30
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

`finish_claim` (`schedule_delivery.py`) answers `False` on any `WatchError`, the same answer it
gives a stale claimant. Two writers change a FIRING record while keeping its claim token:
`ack_item` and, since a chat's delete clears it as the origin of its items, `detach_session`. When
either commits between `finish`'s read and its `EXEC`, the ticker reads `False` as a lost claim,
neither delivers nor releases, and the item stays FIRING until its lease ends and it fires again,
so a reminder arrives one lease late and a task runs twice. `snooze` and `edit` answer `False` the
same way when a detach commits inside their window, which the caller reports as a refused change.

Reproduced on 2026-10-29 with `fakeredis` and the contract suite's `_poke_on_decode` helper: a
claimed recurring item whose record was rewritten with `session_id` cleared and the same token
during `finish` made `finish` return `False` and left the item in the FIRING index. The window is
one Redis round trip, so the race is rare.

## What to do

1. Have `finish_claim` read the record again after a `WatchError` and continue while the live token
   is still the claim's, as `detach_session` does, so only a new claimant makes it answer `False`.
2. Decide whether `snooze` and `edit` read again the same way, and add a raced row for each to
   `test_schedule_store_contract.py`.

## History

- 2026-10-29: filed from the audit of the delete-time detach of a chat's scheduled items.
- 2026-10-30: done, and wider than filed: `release` and `ack` answered `False` the same way, so a
  shown toast whose ack met a detach stayed deliverable and was shown again. Every transition but
  the claim now goes through `fenced` (`schedule_claims.py`), which reads the record and checks the
  guard again after a `WatchError`, so only a cancel, a new claim or a later fire makes one answer
  `False`. A raced claim still answers nothing and the next poll takes it, because its guard
  cannot tell a lease that ran out from one taken a moment ago. Reproduced on fakeredis and on a
  throwaway `redis:8-alpine`, where finish, release, snooze, edit and ack all answered `False`
  before the change and `True` after it; raced rows for each are in
  `test_schedule_store_contract.py`, and ADR-0025 decision 1 states the rule.
