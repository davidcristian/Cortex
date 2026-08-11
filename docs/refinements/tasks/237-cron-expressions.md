# Cron expressions

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** a rule the calendar shape cannot express turns up.

Recorded inside the calendar-recurrence entry, which rejected cron for its first shape and left
this as its one remainder, and restated by the per-rule-timezone entry as the only calendar
remainder still open.

Cron was rejected (a parser dependency, and a syntax a small model gets subtly wrong in ways
that still validate).

Remaining: **cron expressions** if a rule this shape cannot express ever turns up.

Remaining: a **per-rule DST-policy override** is not owed (the fold policy is inherited), so
only **cron expressions** stay open, as every calendar entry left them.

## Trail

- 2026-07-14: Recorded as the calendar-recurrence entry's one remainder, cron itself having been
  rejected there as a parser dependency and a syntax a small model gets subtly wrong in ways that
  still validate.
- 2026-07-15: The per-rule timezone landed and left this as the only calendar remainder, a
  per-rule DST-policy override not being owed.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against
  the tree and fired nothing.
