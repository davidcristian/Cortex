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

## Live rows for the note, written before the first draw, 2026-11-08

The stack brain is rebuilt from the working tree that appends "(The reminder set in this turn is
for one day only. Ask to make it weekly if you meant every week.)" when a turn's `schedule_task`
call with no repeat field runs after the weekly reader refused a call in that turn. One draw per
chat, every card approved, items read back from Redis, calls from the brain's `tool.invocation`
lines, the note read from the reply the driver records. The draws run on Sunday 2026-11-08.

| Row | Message | Draws |
| --- | --- | --- |
| F1 | `Remind me Tuesday at 8 to stretch, keep it going.` | 4 |
| F2 | `Remind me Tuesday at 8 to stretch, all the time.` | 4 |
| W1 to W4 | the W rows of [schedule-one-time-weekday.md](schedule-one-time-weekday.md) | 1 each |

**The form** is a draw whose turn stores a one-time item after a weekly refusal. Its count is
recorded per row and is not part of the rule.

**Rule.** The build ships only if every draw that shows the form ends its reply with the note, no
draw whose turn had no weekly refusal shows it, and no draw whose only item stored after a
refusal repeats weekly shows it. With no form in twelve draws the first part is met by no draw,
and the tests over fakes stay its evidence.

## Results of the live rows

Stack brain image `6b8be04027e3`, built from the working tree at 06:20, draws from 06:21 to
06:26, chats `s11-*`, SM clock 0.57 of `clocks.max.sm` after every draw.

| Row | Calls | Stored | Note |
| --- | --- | --- | --- |
| F1 | 4 weekly refused; 3 retried the weekly rule, 1 `at` 2026-11-10T08:00 | 3 weekly Tuesday 08:00, 1 one-shot | in the one-shot draw only |
| F2 | 4 weekly refused; 2 retried the weekly rule, 2 `at` 2026-11-10T08:00 | 2 weekly Tuesday 08:00, 2 one-shot | in the two one-shot draws only |
| W1 to W4 | one `at` each, none refused | one-shot on the date and hour wanted | in none |

**Result.** The rule passes. The form came in 3 of 12 draws (s11-f1d, s11-f2b, s11-f2d), and
each reply ended with the note; none of the five weekly retries and none of the four W draws
showed it. Log `draws.log`, records `draws.jsonl`, items `items.tsv` and calls `calls.py` over
`brain-draws.log` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot11/`;
every item and row of the draws was deleted.

## The follow-up the note asks for, written before the first draw

Whether "Make it weekly." in the same chat, after a draw that shows the form and the note, leaves
one weekly rule on Tuesday at 08:00 and no one-time item, so the person is not reminded twice on
2026-11-10. Up to eight first turns with F2's message on the same build, chats `s11-u*`; each
that shows the note gets the follow-up. Items are read from Redis with their status after the
follow-up. This is a measurement of the shipped note and changes nothing; a follow-up that leaves
both items, or no weekly rule, is filed as a task with its reproduction.

**Result of the follow-up.** Draws from 06:31 to 06:36, SM clock 0.57 of `clocks.max.sm`. All
eight first calls were refused; 6 of 8 retries stored a one-time `at` 2026-11-10T08:00 and showed
the note, and 2 kept the weekly rule with no note. Each of the six follow-ups called
`list_scheduled`, then `edit_scheduled` on the one-time item's id with `at_time` 08:00 and
`on_days` `["tue"]`, and left one pending weekly rule on Tuesday at 08:00 and no other item. Log
`follow.log`, records `follow.jsonl` and items `follow-items.tsv` in the slot directory above.

## The note's text when a turn also stores a weekly rule

The weekly refusal is sent once per turn, so a second call with `on_days` runs. A turn that stores
a one-time item after the refusal and also a weekly rule, in either order, still shows the note,
which now opens "(A reminder set in this turn is for one day only." and so is true of both items.
Of the 16 retries recorded above, 7 kept `on_days` and 9 stored a one-time `at`; no draw stored
both, and the 5 retries in the start build's proxy log (`req.log` in the stack's `logs/`) all
used `at`. The tests over fakes in `test_schedule_weekly_once.py` are the evidence for both orders.
`STORED_TIME_NOTE`, `MONTHLY_STORED_NOTE` and `WEEKDAY_OFF_NOTE` open the same way ("A reminder",
"Un rappel", "Eine hier erstellte", "Un recordatorio", "Un memento"), since a turn may store two items
and each note names only one.
