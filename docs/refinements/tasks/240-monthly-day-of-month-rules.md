# Monthly day-of-month rules

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 monthly
addendum](../../adr/ADR-0025-scheduling-reminders.md). The calendar rule named a wall time and a
set of **weekdays**, so its search was bounded to one week and "on the 1st of every month" had
no expression but a 30 day interval, which is the drift the rule shape exists to avoid. The
day set became a closed union (`DaySelector = Weekdays | MonthDays`) on `CalendarRule.on`,
model-facing as an `on_month_days` list of integers on both `schedule_task` and
`edit_scheduled`, refused alongside `on_days`. The cheaper-looking `month_days` field beside
the existing `days` was rejected because it makes a monthly rule carry a weekday set it
ignores (the type stating a falsehood, and "exactly one selector" demoted from a shape to a
cross-field check); the union is also where a **yearly** variant joins. **A day the month
lacks clamps to that month's last day rather than skipping the month**, which is not a new
policy but the one daylight saving already set here (an irregularity moves an occurrence and
never deletes one), decided on asymmetric failure modes: skipping means a monthly reminder
silently never fires in up to five months of the year. Two properties fell out rather than
being designed: `[31]` **is** "the last day of every month", so no separate last-day selector
is owed, and days that clamp together fire once, since the walk works in resolved dates. The
walk stays total by construction rather than by a cap (each selector answers
`walk(start) -> (candidates, wrapped)`, the fallback being later than any instant `start`
names), so `next_calendar_due` keeps one body and no unreachable branch. The codec
distinguishes the selectors by **which key is present** (`days` versus `month_days`), so
records predating this decode as weekly and a weekly rule still encodes byte-identically; no
version bump, no migration. `schedule_day_args.py` split out of `schedule_args.py` at the
300-line cap, shared by creation and the edit verb. CI-gated at 100% with the new guards
mutation-proven, DST and local-date cases on both sides of UTC, and the codec's
backward-compatible read tested against a hand-written pre-addendum record.
