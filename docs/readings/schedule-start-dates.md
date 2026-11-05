# Schedule start dates

Whether a repeat the person asks to start on a later day is stored with its first fire on or after
that day. `schedule_task` takes `starting`, an ISO date, beside `at_time`
([ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md) decision 2); a fixed interval names its
first fire in `at`.

## Rows and pass rule, written 2026-11-05 before the draw

Each row is one message in a new session on 2026-11-05, cards approved, three draws per row. A
draw passes when the first `due_at` it stores is on or after the named start; a draw that stores
nothing is a null and is counted apart.

| Row | Message | Named start |
| --- | --- | --- |
| S1 | `Remind me to pay the gas bill on the 15th, starting 15 June.` | 2027-06-15 |
| S2 | `Starting May 1, remind me on the 1st to pay rent.` | 2027-05-01 |
| S3 | `From 3 March, remind me every 4 weeks to change the water filter.` | 2027-03-03 |

- Every stored draw passes: the brain's reply check is not needed; close the task.
- Any stored draw fails: build the typed reply check with a brain-appended note.
- Only nulls: the rows decide nothing; record the refusals.

## Result, 2026-11-05

Drawn 05:51 to 05:58 UTC on a candidate brain built from the change that added `starting`, cortex
gemma-4-12B, temperature as deployed; SM clock about half its maximum at each row's end
(`nvidia-smi --query-gpu=clocks.sm,clocks.max.sm`). Rows and stored items:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot15/rows.jsonl`
and `items.log` beside it.

| Row | Stored first `due_at` per draw | Pass | Null |
| --- | --- | --- | --- |
| S1 | none; 2027-06-15 09:00; 2027-06-15 09:00 | 2 of 2 | 1 |
| S2 | 2027-05-01 09:00; 2027-05-01 00:00; 2027-05-01 09:00 | 3 of 3 | 0 |
| S3 | 2027-03-03 09:00; 2027-03-03 00:00; 2027-03-03 09:00 | 3 of 3 | 0 |

- Every stored draw passed, and each reply named the stored start year. S1, S2 and the rule rows
  used `starting`; S3 used `at` with `every_seconds` 2419200.
- The S1 null: the first call wrote `starting` 2026-06-15, was refused as past with today's date,
  and the reply asked whether to start on 15 June 2027.
- Two stored draws used 00:00 for a request that named no time.
