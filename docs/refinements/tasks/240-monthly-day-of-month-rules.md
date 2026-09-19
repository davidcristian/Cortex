# Monthly day-of-month rules

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Decided in [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 3. The calendar
rule named a wall time and a set of weekdays, so its search covered one week and "on the 1st of
every month" could only be written as a 30-day interval, which is exactly the slippage the rule
shape exists to avoid. The day set became a closed union (`DaySelector = Weekdays | MonthDays`) on
`CalendarRule.on`, offered to the model as an `on_month_days` list of integers on both
`schedule_task` and `edit_scheduled`, refused alongside `on_days`. A cheaper-looking `month_days`
field beside the existing `days` was rejected because it gives a monthly rule a weekday set it
ignores, which makes the type state something false and turns "exactly one selector" from a shape
into a cross-field check. The union is also where a yearly variant fits.

A day the month does not have moves to that month's last day rather than skipping the month. This
is the policy daylight saving already set here, that an irregularity moves an occurrence and never
deletes one, and it rests on the failure modes: skipping means a monthly reminder silently never
fires in up to five months of the year. Two properties followed from the design rather than being
chosen: `[31]` is "the last day of every month", so no separate last-day selector is needed, and
days that resolve to the same date fire once, since the walk works in resolved dates. The walk is
total because each selector returns `walk(start) -> (candidates, wrapped)` with a fallback later
than any instant `start` names, rather than because of a cap, so `next_calendar_due` keeps one body
and no unreachable branch.

The codec tells the selectors apart by which key is present (`days` or `month_days`), so older
records decode as weekly and a weekly rule still encodes to the same bytes: no version bump, no
migration. `schedule_day_args.py` split out of `schedule_args.py` at the 300-line cap and is shared
by creation and the edit verb. Tested at 100% coverage with the new checks proven by mutation,
daylight-saving and local-date cases on both sides of UTC, and the codec's backward-compatible read
tested against a hand-written record from before the key existed.
