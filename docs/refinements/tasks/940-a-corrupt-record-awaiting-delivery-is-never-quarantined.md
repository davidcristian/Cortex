# A corrupt record awaiting delivery is never quarantined

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-29

Only the claim path quarantines a schedule record that does not decode, and `claim_due`
(`schedule_claims.py`) reads only the due and firing indexes. A record listed only under
`cortex:schedules:deliverable`, which is a fired one-shot waiting for its ack, is never read there.
`deliverable_items` and `list_active` decode every record they list and raise on one that fails, so
that record fails every `ListDueReminders` call, every `schedule_task` and every `list_scheduled`
for as long as it stays. A chat's delete skips it, so it also keeps a deleted chat's id. A corrupt
record that is still due fails `list_active` the same way until it falls due and is quarantined.

Reproduced on 2026-10-29 with `fakeredis`: a raw `not json` record at `cortex:schedule:poison`,
listed only under the deliverable key. `detach_session("session-1")` returned 0, `deliverable()`
and `list_active()` raised `ScheduleStoreError`, and after `claim_due` at one hour, one day and one
year later `dead_letters()` was still empty.

## What to do

1. Have `deliverable_items` and `list_active` stop raising on a record that does not decode, so one
   record costs one item, and add a contract row for each that seeds the record under the
   deliverable key.
2. Decide whether those read paths move the record to the dead-letter hash through `quarantine`,
   or only skip and log it while another pass moves it, and write the choice into ADR-0025.

## History

- 2026-10-29: filed from the audit of the chat delete that skips a record that does not decode.
