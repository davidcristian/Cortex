# The yearly date refusal lets a second date in one turn repeat monthly

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

The `YEARLY_DATE` refusal (`_unasked_refusal` in `dispatch_round.py`) refuses only the first
`schedule_task` call with `on_month_days` in a tool loop, and every later one runs, whatever date
it is for. A message with two yearly dates gets one refusal: for "Remind me of
Anna's birthday on 11 May and of Tom's birthday on 3 June.", calling `_unasked_refusal` on one
`LoopRecord` with a monthly call for Anna (`on_month_days` [11]) returns `YEARLY_DATE`, and a
second monthly call for Tom (`on_month_days` [3]) returns `None` and runs. Tom's birthday then
fires every month. The field `LoopRecord.yearly_refused` already holds the refused calls, but only
its emptiness is read. The deep phase builds its own `LoopRecord`, so its first monthly call is
refused again after the cortex's call ran.

## What to do

1. Write rows into the readings first: requests naming two yearly dates, scored by how many
   stored rules are monthly, beside the Y and M rows of the readings.
2. Then try refusing each monthly call whose `text` differs from every refused one, so a retry of
   the same reminder still runs, and draw it on those rows and on the monthly requests of
   R-982, where a refusal per reminder must not make the cortex give up the monthly rule.

## History

- 2026-11-05: filed by the closing audit from a unit reproduction against `dispatch_round.py`.
