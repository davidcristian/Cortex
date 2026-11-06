# The wrong-date refusal of a one-time reminder names fields the call has not

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-06

`offset_date_wrong` (`schedule_offset.py`) now refuses a `schedule_task` call whose one-time `at`
falls on a MM-DD other than the one the message wants, but the result the model reads is still
written for the `on_dates` form. `OFFSET_DATE_MSG` says "this call's 'on_dates' holds another date",
and `offset_refusal` ends "Call again with that date in 'on_dates' and the same 'at_time'". For the
call `{"text": "t", "at": "2027-02-14T09:00:00Z"}` on "My sister's birthday is 14 February, remind me
three days before", `offset_date_wrong` returns `True` and the call has neither field, so the model
is told to fix a field it did not send and to retry as a yearly rule when it stored a one-time item.
Reproduction: a script that prints `offset_date_wrong` and `offset_refusal` for that call, in slot 13
of the run's scratch directory (`repro994.py`, `repro994.out`). No test in
`test_schedule_offset.py` reads the refusal text for an `at` call; the three refused-then-retry rows
check only `OFFSET_DATE_MSG` as the audit detail.

## What to do

Pass the refused call into `offset_refusal` (through `_told` in `dispatch_round.py`) so the text
names the field the call used: `at` with a full date-time on the wanted MM-DD for a one-time call,
`on_dates` with the same `at_time` for a yearly one. Keep one `OFFSET_DATE_MSG` prefix, which
`handoff_view.py` matches with `startswith` to find the refused calls in a record's tail, and word
it for both forms. Tests first: the `at` form's refusal names `at` and not `on_dates`, the
`on_dates` form is unchanged, and the tail reader still finds both. Rebuild the stack brain and
draw A1 on a candidate to see the retry keep its one-time shape.

## History

- 2026-11-06: filed by the second audit of the night's commits, from the one-time `at` reading
  added to the offset check the same night.
