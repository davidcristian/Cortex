# Readings: what the cortex calls after a weekly refusal it should not have had

Whether the cortex keeps a weekly rule the person asked for in words `_MAY_REPEAT`
(`brain/packages/core/src/cortex_core/schedule_weekly.py`) does not read, once `weekly_unasked`
has refused its first call. A tool refusal keeps the tool when unsure: if the retry keeps the
rule, a missed repeat word costs one round; if it switches to a one-time `at`, the repeat is lost
with nothing shown. Read with [schedule-one-time-weekday.md](schedule-one-time-weekday.md), whose
replay rows B1 to B4 this follows.

## Rows and the rule, written before the first draw, 2026-11-08

Each row sends request 110 (recorded through the proxy from a second brain built from
`838d7085c`, rows B1 and B2) straight to the model host four times, with its message, its first
call (`on_days` `["tue"]`, `at_time` 08:00) and its result changed as named, and reads the next
call. The result is the current weekly refusal: `WEEKLY_DAY_MSG` and "The next Tuesday is
2026-11-10.".

| Row | Message | Next call wanted |
| --- | --- | --- |
| F1 | `Remind me Tuesday at 8 to stretch, keep it going.` | `on_days` `["tue"]` at 08:00 |
| F2 | `Remind me Tuesday at 8 to stretch, all the time.` | `on_days` `["tue"]` at 08:00 |

**Rule.** If at least 2 of the 8 next calls are a one-time `at` or no call, a refused weekly rule
is lost often enough that the shape changes: the refusal gets a note the brain appends when a turn
it fired in stores a one-time item, or becomes that note alone. With at most 1 of 8, the retry
keeps the rule, and a missed repeat word costs one round.

## Results

SM clock 0.57 of `clocks.max.sm` before, 0.60 after. Log `replayf.log` and records
`replayf.jsonl` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot10/`.

| Row | Next call, four draws |
| --- | --- |
| F1 | 3 `at` 2026-11-10T08:00, 1 `on_days` `["tue"]` at 08:00 |
| F2 | 2 `at` 2026-11-10T08:00, 2 `on_days` `["tue"]` at 08:00 |

**Result.** 5 of 8 next calls dropped the repeat for a one-time `at` on the named date, so the
rule calls for the shape change. A word added to `_MAY_REPEAT` fixes only the form it names, and
`named_weekday` is shared with the weekday reader, so each word also stops that reader. A refusal
only beside a one-time marker (`on`, `this`, `next`, `am`, `el` before the weekday) does not
fit either: of 11 recorded draw messages naming one weekday and no repeat word, 5 have no marker,
among them the French bare weekday (`Rappelle-moi mardi à 9h`, a one-time request) and the
audit's `the evening ahead of Tuesday's dentist appointment`, whose weekly call on Monday the
refusal caught correctly.
