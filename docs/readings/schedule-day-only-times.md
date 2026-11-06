# Schedule times for a request that names a day and no time

Which time of day the brain stores when the person names a day and no time of day. The typed
arguments of `schedule_task` and `edit_scheduled` have no missing-time case: a one-time reminder
gives `at`, an ISO-8601 date-time, and every wall-clock repeat gives `at_time`, an `HH:MM`
([ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md)). The spec text says "e.g. 09:00" and
"e.g. 2026-07-12T18:00:00" and names no default, so the model picks the time. In the start date
rows of 2026-11-05 two of eight stored draws used 00:00
([schedule-start-dates](schedule-start-dates.md)).

## Rows and pass rule, written 2026-11-06 before the draw

Each row is one new session on the stack brain (built from the tree at `43c4011b1`), cards
approved, three draws per row, schedule zone UTC. Per draw the record keeps the time of day of
every stored item (`due_at`, and `rule.hour:minute` for a repeat) and whether the reply names a
time of day (a clock figure such as `9:00` or `9 am`, or the word noon or midnight).

| Row | Message | Shape |
| --- | --- | --- |
| D1 | `Remind me on 14 December to post the parcel.` | one time, `at` |
| D2 | `Remind me on the 1st of every month to pay the rent.` | monthly, `on_month_days` |
| D3 | `Remind me every Monday to take the bins out.` | weekly, `on_days` |
| D4 | `From 3 March, remind me every 4 weeks to change the water filter.` | interval from a date |
| D5 | `Remind me of Mia's birthday on 9 August every year.` | yearly, `on_dates` |
| D6 | `Remind me on the 15th of every month to pay the gas bill.` then `Move that to the 20th.` | edit that moves the day |

A draw passes when every item it stores has a time of day other than 00:00 and the reply names
the time of day it stored. A draw that stores nothing is a null and is counted apart. A candidate
for the missing-time case ships only when every stored draw of these rows passes on it and no row
stores fewer draws than the baseline did.

- The baseline stores 00:00 in any draw: the task builds its remedy, and the rows above measure it.
- The baseline stores no 00:00 in 18 draws: the two draws of 2026-11-05 are recorded as not
  reproduced and the task is left open for the next time a draw shows one.
- Only nulls: the rows decide nothing; record the refusals.

## Result, 2026-11-06

Drawn 02:01 to 02:08 UTC on the stack brain (tree at `43c4011b1`), cortex gemma-4-12B, temperature
as deployed, no candidate; SM clock between 0.54 and 0.57 of its maximum at each draw's end
(`nvidia-smi --query-gpu=clocks.sm,clocks.max.sm`). Rows, stored records and the clock readings:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot2/rows.jsonl`,
`records.jsonl` and `rows.clock` beside it; the calls are in the stack brain's `tool.invocation` log
lines from 02:01:30 UTC.

| Row | Stored time of day per draw | Reply names the time | At 00:00 |
| --- | --- | --- | --- |
| D1 | 09:00; 09:00; 09:00 | 0 of 3 | 0 |
| D2 | 09:00; 09:00; 09:00 | 3 of 3 | 0 |
| D3 | 09:00; 09:00; 09:00 | 3 of 3 | 0 |
| D4 | 09:00; 09:00; 09:00 | 0 of 3 | 0 |
| D5 | 09:00; 09:00; 00:00 | 2 of 3 | 1 |
| D6 | 09:00; 09:00; 09:00 (after the edit) | 0 of 3 | 0 |

- 18 stored draws, no null, one at 00:00: D5 draw 3, where the first call wrote `on_month_days`
  [9] with `at_time` 00:00, was refused by the yearly date check, and the retry with `on_dates`
  kept 00:00; its reply named no time. Over both nights, 3 of 26 stored day-only draws are at 00:00.
- The reply named the time in 8 of 18 draws ("at 9:00 AM" or "at 09:00"): every D2 and D3 draw and
  two D5 draws, never the one-time D1, the interval D4 or the edit D6.
- D6, all three draws: the first `edit_scheduled` call gave `on_month_days` [20] and no `at_time`,
  was corrected with the typed "apply only together with 'at_time'" text, and the retry gave
  `at_time` 09:00 (the stored time, which `list_scheduled` had shown) with `on_month_days` [20].
  Every edit took two calls to move a day; recorded as task 990.
- Under the pass rule, no row passes in every draw: D1, D4 and D6 fail on the unnamed time alone.
  The task's remedy is to be built and drawn on these rows.
