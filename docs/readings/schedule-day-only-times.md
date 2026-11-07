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
  Every edit took two calls to move a day.
- Under the pass rule, no row passes in every draw: D1, D4 and D6 fail on the unnamed time alone.
  The task's remedy is to be built and drawn on these rows.

## Result of the kept-time edit, 2026-11-06

Row D6 was redrawn three times, 02:21 to 02:23 UTC, on a candidate brain built from the tree with
the edit verb filling a missing `at_time` (and `in_zone`) from the item's own rule when the call
gives a day selector alone; SM clock at 0.57 of its maximum at each draw's end. Each draw made
three calls: `schedule_task`, `list_scheduled`, `edit_scheduled`. Every `edit_scheduled` call gave
`on_month_days` [20] and no `at_time`, ran at once and kept the stored time of day (09:00; 12:00;
09:00, where the first call of draw 2 had chosen 12:00). One call per edit, against two in every
baseline draw. No reply named the time (0 of 3), so the row still fails the pass rule on the
unnamed time alone. Rows, records and clock readings:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot3/rows.jsonl`,
`records.jsonl` and `rows.clock` beside it.

## Result of the 00:00 refusal, 2026-11-06

Rows D1 to D6 were drawn twice each, 02:40 to 02:44 UTC, on a candidate brain built from the tree
with a typed refusal: a `schedule_task` or `edit_scheduled` call whose `at_time` or `at` time of
day is 00:00, when the message names no midnight form (`midnight`, `0:00`, `00:00`, `12 am`,
`12:00 am`, `12 a.m.`), is refused once per turn with a result that names the 09:00 default and
asks for the time the person meant, and a second such call runs. SM clock at 0.57 of its maximum
at each draw's end. Rows, records, clock readings and the candidate's patch and test file:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot4/`.

| Row | Stored time of day per draw | Reply names the time | At 00:00 |
| --- | --- | --- | --- |
| D1 | 09:00; 09:00 | 0 of 2 | 0 |
| D2 | 09:00; 09:00 | 2 of 2 | 0 |
| D3 | 09:00; 09:00 | 2 of 2 | 0 |
| D4 | 09:00; 09:00 | 0 of 2 | 0 |
| D5 | 09:00; 09:00 | 1 of 2 | 0 |
| D6 | 09:00; 09:00 (after the edit) | 0 of 2 | 0 |

- 12 stored draws, no null, none at 00:00. The refusal was written once, in D5 draw 1, on the
  baseline's own failing shape: the first call wrote `on_month_days` [9] with `at_time` 00:00 and
  was refused by the yearly date check, the retry wrote `on_dates` ["08-09"] with `at_time` 00:00
  and was refused for the unasked 00:00, and the third call wrote `at_time` 09:00 and ran; the
  reply named "9:00 AM". Every other call gave 09:00 at once: 14 calls over the 12 draws, one
  `edit_scheduled` per D6 edit.
- The reply named the time in 5 of 12 draws: both D2, both D3 and one D5, never D1, D4 or D6, as
  in the baseline.
- Under the pass rule the refusal alone does not ship: no draw stored 00:00 and no row stored
  fewer draws than the baseline, but D1, D4 and D6 fail on the unnamed time, which the refusal
  does not change. The appended time was built on top of it and the two were drawn together.

The refusal as built (`schedule_midnight.py`, the `MIDNIGHT_TIME` member of `DispatchRefusal`):
`midnight_unasked` is true for a `schedule_task` or `edit_scheduled` call whose `at_time` is
`00:00` or `0:00`, or whose `at` ends in a 00:00 time, when `names_midnight` finds none of
`midnight`, `0:00`, `00:00` (not followed by am or pm), `12 am`, `12:00 am` or `12 a.m.` in the
person's message. `run_round` refuses the first such call of a turn with the result "REFUSED: this
call sets the time of day to 00:00 and the person named no midnight, so it was not run. A reminder
at 00:00 fires while the person is likely asleep. Call again with the time of day the person
meant, or with the default 09:00 in the schedule zone when they named none." and runs the second,
so it fails toward storing the reminder; the deep phase reads the turn's refusal from the handoff
tail (`midnight_refused_calls`).

The refusal's 38 tests, each of nine mutations failing at least one (dropping the `12 am` form,
dropping the am or pm guard after `00:00`, reading every schedule call as 00:00, not reading
`at_time` `0:00`, refusing the named midnight instead, refusing every 00:00 call, forgetting the
refusal, reading the yearly refusals from the handoff tail instead, and the deep phase forgetting
the tail's refusal):

- `names_midnight` is true for `tonight at 0:00`, `at 12 am`, `at midnight`, `at 00:00`,
  `at 12:00 am`, `at 12am` and `at 12 a.m.`, and false for `at 12 pm`, `at 12:00 pm`, `at 12:00`,
  `at 10:00`, `at 00:00 pm`, the D1 message and the D3 message.
- `sets_midnight` is true for `at` `2026-12-14T00:00:00`, `2026-12-14T00:00:00Z`,
  `2026-12-14T00:00+01:00` and `2026-12-14 00:00`, for `at_time` `00:00` or `0:00`, and for an
  `edit_scheduled` call with `at_time` `00:00`; false for `at` `2026-12-14T09:00:00`,
  `2026-12-14T00:30:00` and `2026-12-14T10:00:00`, `at_time` `09:00`, a non-string `at`,
  `in_seconds` alone, an edit that moves a day without `at_time`, and another tool with `at_time`
  `00:00`.
- In the loop, the first 00:00 call for the D1 message is refused with the message and a second
  00:00 call runs; a retry at 09:00 runs; a 00:00 call runs at once when the message names
  midnight or the call gives 09:00; the deep phase reads the refusal from the handoff tail, so a
  deep retry at 00:00 runs and a first deep 00:00 call is refused.

## Row added 2026-11-06 for the next draw

| Row | Message | Shape |
| --- | --- | --- |
| D7 | `Remind me at midnight on 14 December to post the parcel.` | one time, a named midnight |

A D7 draw passes when every item it stores is at 00:00 and the reply names midnight; the pass rule
for D1 to D6 is unchanged. The next candidate holds the recorded refusal and the appended time,
and is drawn on D1 to D7.

## Result of the refusal with the appended time, 2026-11-06

Rows D1 to D7 were drawn twice each, 03:05 to 03:10 UTC, on a candidate brain built from the tree
with the 00:00 refusal and a closing note: `run_round` sets `TaintLedger.stored_time` to the
`HH:MM` in the `due` time of a successful `schedule_task` call given `at` or `at_time`, or of an
`edit_scheduled` call, and `limit_notes` appends `STORED_TIME_NOTE` ("The reminder set or changed
in this turn is at HH:MM. Ask to change it if you meant another time of day.") when the reply
names no clock figure, am or pm, noon or midnight (`names_time_of_day` in `schedule_claim.py`).
The field crosses a handoff with the ledger. SM clock at 0.57 of its maximum at each draw's end.
Rows, records and clock readings:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot5/rows.jsonl`,
`records.jsonl` and `rows.clock` beside it.

| Row | Stored time of day per draw | Reply names the time | At 00:00 |
| --- | --- | --- | --- |
| D1 | 09:00; 09:00 | 2 of 2, both by the note | 0 |
| D2 | 09:00; 09:00 | 2 of 2 | 0 |
| D3 | 09:00; 09:00 | 2 of 2 | 0 |
| D4 | 09:00; 09:00 | 2 of 2, both by the note | 0 |
| D5 | 09:00; 09:00 | 2 of 2 | 0 |
| D6 | 09:00; 09:00 (after the edit) | 2 of 2, both by the note | 0 |
| D7 | 00:00; 00:00 | 2 of 2, midnight | 2 |

- 14 stored draws, no null. D1 to D6: none at 00:00, and every reply names the stored time, in the
  model's own text in 6 (D2, D3, D5) and by the appended note in 6 (D1, D4, D6). D7: both draws
  stored 00:00 and named midnight. The 00:00 refusal was written in no draw, since every call gave
  09:00 at once (D4 draw 2's first call gave `at_time` with `every_seconds` and was corrected by
  the typed text; D5 draw 1's first call was refused by the yearly date check, as in the baseline).
- Under the pass rule both ship: every stored draw of D1 to D6 passes, both D7 draws pass, and no
  row stored fewer draws than the baseline.

## Two combined turns on the stack brain, 2026-11-06

The closing audit sent two turns to the stack brain at 05:05 UTC (SM clock at 0.57 of its maximum),
rows `rows.jsonl`, `records.jsonl` and `rows.clock` in slot 11 of the run's scratch directory, the
records deleted after the read.

- "Remind me to pay the rent on the 1st of every month", then "Move the rent reminder to the 3rd" in
  the same session: `schedule_task` with `at_time: 09:00`, `on_month_days: [1]`; then `list_scheduled`
  and `edit_scheduled` with `on_month_days: [3]` and no `at_time`. The stored rule read back as
  `hour 9, minute 0, month_days [3]`, due 2026-12-03T09:00 UTC. The first reply named 9:00 AM; the
  second named no time and got the appended note "at 09:00".
- "Remind me at midnight on 31 December to call Anna": `schedule_task` with
  `at: 2026-12-31T00:00:00`, not refused since the message names midnight, stored due
  2026-12-31T00:00 UTC, and the reply named midnight, so no note was appended.

## The second audit's two combined turns, 2026-11-06

Sent again at 05:29 UTC to the stack brain built from the night's last brain commit (SM clock at
0.53 to 0.57 of its maximum), rows in slot 13 of the run's scratch directory, records deleted after
the read. The rent pair stored `hour 9, minute 0, month_days [3]` after `list_scheduled` and
`edit_scheduled` with `on_month_days: [3]` and no `at_time`; the first reply named 9:00 AM, the
second named no time and got the appended note "at 09:00". The midnight turn stored a one-time
`at` due 2026-12-31T00:00 UTC with no refusal, and the reply named midnight, so no note.

On 2026-11-07 at 06:42 UTC, on the stack brain rebuilt with the hour written with h read only
after a word for a point in time (SM clock 0.57 of `clocks.max.sm`), the French request
`Rappelle-moi le 20 novembre que le trajet prend 1h30.` stored a reminder at 09:00 and replied
`D'accord, je vous rappellerai le 20 novembre que le trajet prend 1h30.` with the note "at 09:00"
appended. The reader before it read `prend 1h30` as a clock time and left that note out.
