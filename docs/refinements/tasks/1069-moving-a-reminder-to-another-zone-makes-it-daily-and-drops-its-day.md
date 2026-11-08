# Moving a reminder to another zone makes it daily and drops its day

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`edit_scheduled` takes a zone only as `in_zone` beside `at_time`, and its `at` (the move that keeps
a one-time item one time) reads the default zone. On 2026-11-08, on the stack brain from
`0d6efa10e` (chat `s18-z1`, cards approved), `Remind me on Wednesday at 9:00 to send the parcel.`
stored a one-time item due 2026-11-11T08:00Z. The follow-up `Actually make that 9:00 New York
time.` made an `edit_scheduled` call with `at_time` and `in_zone` `America/New_York`, which stored
a daily rule due 2026-11-08T14:00Z, today rather than Wednesday. The reply was `OK. I've updated
that reminder to 9:00 AM New York time.` with `DAILY_STORED_NOTE` under it, which is true; nothing
said the reminder had moved from Wednesday to today.

The same build has a refusal of `in_zone` beside `at`, which asks for the zone as an offset in
`at`, so a model that tries `at` first is now told how to write it.

## What to do

1. Decide how a one-time item moves to another zone's wall clock: name the offset form in the
   `edit_scheduled` description beside `at`, or let `at` take `in_zone` for an `at` with no offset.
2. Write rows and a rule into the readings, then draw the s18-z1 pair 8 times on each build.

## History

- 2026-11-08: filed by the audit of tonight's schedule changes, from one live flow.
