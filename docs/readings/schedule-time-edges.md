# Readings: schedule times at the edges of the clock

How a reminder's time is read, stored and fired around a daylight saving change, around midnight,
and across the zones the host, the brain container and the model each use. Read with
[ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md) (the display zone and the fold policy)
and [ADR-0025](../adr/ADR-0025-scheduling-reminders.md) (the store and the ticker). The tools are
`brain/packages/core/src/cortex_core/schedule_tools.py` and `schedule_args.py`.

## The rig

**2026-10-16**, the shared `cortexn6` stack: the resident cortex (gemma-4-12B), Redis schedule
backend, `CORTEX_SCHEDULE_TZ` unset (so `UTC`), and the real Linux shell on `Xvfb`. The host is
in `Europe/Berlin` (CEST, +02:00); summer time ends on 2026-10-25, when 03:00 CEST becomes 02:00
CET and the hour from 02:00 to 02:59 happens twice.

The live clock cannot be moved, so three flows run the real core code under a fixed clock:

- **Core flows** (`slot7/flow12.py` in the run's scratch directory) call `next_occurrence`,
  `parse_schedule`, the creation confirmation and `describe_item` with a `zoneinfo` Berlin zone,
  and ask `InMemoryScheduleStore.claim_due` whether an item is due 5 s after it was made.
- **Cortex draws** (`slot7/flow4.py`) build the real `schedule_task` and `list_scheduled` specs
  with a fixed clock, so the spec states the fixed time, send them with the security preamble and
  one user message to the cortex server through `cortex_inference.request.build_payload`, and
  parse the returned call with `parse_schedule` under the same clock. No memory and no history.
- **Live turns** go through the overlay (`slot3/ask.sh`) to the real brain at the real time.

SM clock during the draws: 0.58 of `clocks.max.sm` (`nvidia-smi --query-gpu=clocks.sm,clocks.max.sm`).

## What each flow decides, written before the first run

| Flow | Question | Expected from ADR-0065 |
| --- | --- | --- |
| T1 | Next fires of daily 09:00 and 02:30 rules, and an 86400 s interval, across 2026-10-25 and the 2027-03-28 gap | 09:00 local every day; 02:30 once on 10-25; the gap fires at 03:30; the interval drifts to 08:00 |
| T2 | What a one-time `at` in the repeated hour, in the gap, and at a past time stores, confirms, lists and fires | repeated hour takes +02:00; gap reads 03:30; a past `at` is accepted and due at once |
| T3 | Which zone the model is told, the container runs in and the overlay shows, and whether "at 23:00" fires at 23:00 local | the default deployment reads every time as UTC |
| T4 | What the cortex writes for "tomorrow at 9" near midnight, "at 2:55" in the second pass of the repeated hour, and "tomorrow at 9" at 00:30 CEST under the UTC default | the stored instant is the one the person meant |

A row in T4 passes when the stored instant equals the wanted one and the call has no `at_time`.
Rows: **A** "Remind me tomorrow at 9 to call the plumber." at 2026-10-24 23:50 CEST in Berlin,
wanted 2026-10-25 09:00 CET. **B** "Remind me at 2:55 to check the oven." at 2026-10-25 02:45 CET
(the second pass) in Berlin, wanted 02:55 CET (01:55 UTC). **C** row A's text at 2026-10-17 00:30
CEST under the UTC zone, wanted 2026-10-18 09:00 local. **D** "Remind me today at 23:00 to check
the oven." and **E** "Remind me at 23:00 to check the oven." at 03:00 UTC under the UTC zone,
wanted 23:00 UTC the same day. **F** "Remind me today at 9 to call the plumber." and **G** "Remind
me at 9 to call the plumber." at 2026-10-24 23:50 CEST in Berlin, written after the first five
rows and before any draw of them, wanted 2026-10-25 09:00 CET or a question; a past `at` fails.

## T1: calendar rules and an interval across the change

| Rule, from | Fires (local) |
| --- | --- |
| daily 09:00, from 10-24 06:00 UTC | 10-24 09:00+02:00, 10-25 09:00+01:00, 10-26 09:00+01:00, 10-27 09:00+01:00 |
| daily 02:30, from 10-24 00:00 UTC | 10-24 02:30+02:00, 10-25 02:30+02:00, 10-26 02:30+01:00, 10-27 02:30+01:00 |
| daily 02:30, from 2027-03-27 00:00 UTC | 03-27 02:30+01:00, 03-28 03:30+02:00, 03-29 02:30+02:00 |
| `every_seconds: 86400`, made 10-24 09:00+02:00 | 10-25 08:00+01:00, 10-26 08:00+01:00, 10-27 08:00+01:00 |

All as ADR-0065 states: the rule keeps 09:00, the repeated 02:30 fires once on its first reading,
the gap fires just past it, and the interval keeps 24 hours and drifts an hour, which the runbook
documents. One edge follows from "fires once": a daily 02:30 rule made at 02:10 CET, in the second
pass, first fires on 10-26, though the wall clock shows 02:30 twenty minutes later. Today's 02:30
already happened, at 00:30 UTC. No defect filed.

## T2: one-time times in the repeated hour, the gap and the past

| `at` | Now (local) | Stored (UTC) | Confirmation and listing | Due 5 s later |
| --- | --- | --- | --- | --- |
| `2026-10-25T02:30:00` | 10-24 22:00+02:00 | 00:30 | 02:30+02:00 (tomorrow) | no |
| `2026-10-25T02:30:00+01:00` | 10-24 22:00+02:00 | 01:30 | 02:30+01:00 (tomorrow) | no |
| `2027-03-28T02:30:00` | 03-27 21:00+01:00 | 01:30 | 03:30+02:00 (tomorrow) | no |
| `2026-10-25T02:55:00` | 10-25 02:45+01:00 | **00:55** | 02:55+02:00 (today) | **yes** |
| `2026-10-25T02:55:00+01:00` | 10-25 02:45+01:00 | 01:55 | 02:55+01:00 (today) | no |
| `2026-10-24T09:00:00` | 10-24 23:50+02:00 | 07:00 | 09:00+02:00 (today) | **yes** |

- **The second pass.** At 02:45 CET a naive 02:55 means ten minutes ahead, but `fold=0` read it as
  02:55 CEST, an hour in the past, and the reminder fired on the next poll. The confirmation
  showed `02:55:00+02:00` with no sign that the time had passed. Fixed in this run (below).
- **A past `at` is accepted.** Nothing compares `at` with now, so a time that has passed is stored
  and fires on the next poll, and the confirmation reads like any other. Fixed in this run (T5).

## T3: the zone chain on the default deployment

| Where | Zone |
| --- | --- |
| host (`/etc/timezone`, `date +%Z`) | Europe/Berlin, CEST |
| brain container (`date`, `TZ`) | UTC, `TZ` unset |
| `CORTEX_SCHEDULE_TZ` (`docker/docker-compose.yml` default) | `UTC` |
| what the model reads (`schedule_task` spec) | "The current date-time is ...+00:00 (UTC)." |
| overlay | shows no times: a reminder card shows its text, and `firedAtUnixMs` is used only to acknowledge it |

Live turn at 05:02 CEST: "Remind me today at 23:00 to check the oven." The cortex called
`schedule_task` with `{"at_time": "23:00", ...}` and replied "I've set a reminder for you to check
the oven today at 23:00." Redis held `due_at` `2026-10-16T23:00:00+00:00` with a daily `rule`:
01:00 CEST on 10-17, two hours after the time the person named, and repeating every day, which
the reply did not say. The item and the turn's memory row were deleted after the reading. Two
defects: the zone, fixed in this run by the stack recipes passing the host's zone
([ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md) decision 5), and the daily rule, fixed
in this run (T5).

## T4: cortex draws under a fixed clock

| Row | Draws | Pass | What the failures wrote |
| --- | --- | --- | --- |
| A | 5 | 5 | |
| B | 5 | 0 | 3 naive `at` `2026-10-25T02:55:00` (stored 00:55 UTC, due at once); 2 `at_time` `02:55` (daily, first fire 10-26) |
| C | 5 | 0 | 5 `at` `2026-10-17T09:00:00`: 11:00 CEST on 10-17, a day early and two hours late by the person's clock |
| D | 10 | 10 | |
| E | 10 | 8 | 2 `at_time` `23:00` (daily) |
| F | 10 | 8, 1 asked | 1 `at` `2026-10-24T09:00:00`, past, due at once; 1 no call that asked whether to use tomorrow |
| G | 10 | 5 | 5 `at_time` `09:00` (daily) |
| B, after the fix | 5 | 5 | 1 wrote `+01:00`, 4 a naive `at`, each stored 01:55 UTC |

- **A** passes: in Berlin the model reads the local date and "tomorrow" is the local tomorrow.
- **C** is the default zone seen from the model: under the UTC zone the model reads 22:30 on 10-16 and is
  right by what it was told.
- **B** and **E** show that a bare time with no day ("at 2:55", "at 23:00") is sometimes written
  as `at_time`, a daily rule. With "today" in the request, D wrote `at` 10 of 10 in a fresh
  context, while the live turn above, with history and memory, wrote `at_time`. G, "at 9" asked
  late at night, wrote `at_time` in half its draws. T5 below fixes it.
- **F** is the past `at` seen from the model: "today at 9" asked at 23:50 wrote the past time
  once in 10, and that reminder fires at once; once it asked instead, which the row counts as a
  pass.

## After the second-pass fix

With `DisplayZone.resolve_after` in `_parse_at` (ADR-0065 decision 1), T2's second-pass row
stores 01:55 UTC, confirms and lists `02:55:00+01:00 (today)`, and is not due 5 s later; the other
T2 and all T1 rows are unchanged. Row B, drawn again on the same cortex, passed 5 of 5 (table
above). The core suite (`brain/packages/core/tests`) holds the tests that fail without it.

## T5: a past `at` and a bare time, with the model seeing the result

Two result changes to `schedule_task`, drawn together in one build, each with its own rule:

- **Past refusal.** An `at` more than 60 s before now is refused with a correction naming the
  current date-time in the display zone, instead of being stored to fire at once.
- **Repeat note.** The confirmation of an `at_time` with no day selector says that the item
  repeats every day, and that `edit_scheduled` with its id and `every_seconds` 0 makes it one time.

They act on different calls: the refusal only on a past `at`, the note only on a daily rule. A
model that answers the note by cancelling and calling again with a past `at` meets the refusal,
so a row can now take two or three calls. Each is backed out alone if its rule fails.

**Driver** (`slot8/draw.py` in the run's scratch directory): T4's fixed clock and specs, plus
`edit_scheduled`, `cancel_scheduled` and `list_scheduled` run against an in-memory store, and up
to five model steps until a reply with no call. A cancel runs without the confirmation card. A
draw is classified by what the store holds at the end and by the reply: the wanted instant as a
one-time item, a past time, a daily rule the reply names ("every day", "daily", "repeat") or does
not name, or no item and a question.

Rows, written before the baseline: T4's **A**, **D**, **E**, **F** and **G**; **H**, row D's text
after one earlier exchange ("What is 5 plus 5?"), the shape of the live turn; and the earlier
readings' rule rows **R1** "Remind me every day at 10:00 to take my vitamins." and **R2** "Remind
me every Monday at 9:00 to send the weekly report." under the UTC zone at 03:00. A draw takes
about 12 s, so the counts are cut from the tasks' 20 to fit the run: A 3, D 3, E 5, F 10, G 10,
H 5, R1 3, R2 3. Both rules count every draw, so they read the same at the smaller count.

- **Rule for the past refusal:** it ships only if every A and D draw still stores its wanted
  instant with one call, and no F draw ends with a past time stored (F passes with the next day's
  09:00 or with no item and a question).
- **Rule for the repeat note:** it ships only if no A, D, E, F, G or H draw ends with a daily rule
  that the reply does not name, and every R1 and R2 draw still ends with its rule.

**Replication for the past refusal, written after the candidate's A draws and before any later
draw.** One candidate A draw took two calls. Its first `at` was "tomorrow at 09:00", which the
ISO check refused, a check neither change touches, and its second call stored the wanted instant.
A draw's first call comes from the same prompt in both builds. A and D are drawn 5 more times
each on the candidate, and the past refusal ships only if all 10 store the wanted instant with
one call, the original rule's letter. Otherwise it is backed out and its task stays open.

### T5 results

SM clock during the draws: 0.61 of `clocks.max.sm`. Each cell counts draws by what the store held
at the end; "named" is a daily rule the reply calls "every day", "unnamed" one it does not.

| Row | Baseline | Both changes |
| --- | --- | --- |
| A | 3 of 3 wanted, one call | 3 of 3 wanted, 1 in two calls (ISO check); replication 5 of 5, one call |
| D | 3 of 3 wanted, one call | 3 of 3 wanted, one call; replication 5 of 5, one call |
| E | 3 wanted, 2 named | 5 wanted (1 after `edit_scheduled`) |
| F | 9 wanted, **1 unnamed**, 0 past | 7 wanted (1 after the ISO check), 2 named, 1 asked, 0 past |
| G | 5 wanted, 5 named | 4 wanted (1 after `edit_scheduled`), 6 named |
| H | 4 wanted, **1 unnamed** | 5 wanted (1 after `edit_scheduled`) |
| R1, R2 | 3 and 3 rules | 3 and 3 rules |

- **The repeat note passes its rule**: no unnamed daily rule in 36 one-time draws, against 2 in
  the baseline's 36, and every rule row kept its rule. The baseline's two unnamed draws are the
  live turn's defect: H replied "today at 23:00" over a daily rule. Under the note, E, G and H
  each turned one daily rule into one time with `edit_scheduled`. G still keeps a daily rule in 6
  of 10 and says so ("every day at 9:00 AM"), which the person can now see and correct.
- **The past refusal passes on its replication.** No draw in either build wrote a past `at`, so
  the refusal never fired in the rows. A side row, not under the rule, put the refusal in front of
  the model: F's text with a seeded call for `2026-10-24T09:00:00` and its refusal, 5 draws. Four
  asked whether to use 09:00 tomorrow; one stored a daily 09:00 rule and named it. None stored a
  past time or claimed one was set. One reply in the F row said "today at 9:00 AM" over a rule
  due tomorrow, a wording slip the rules do not count, drawn as T6.
- Both changes shipped. The core suite (`brain/packages/core/tests`) holds the tests that fail
  without them.

## T6: the day the creation confirmation names

**Candidate.** The creation confirmation adds the due time's day counted from today, as a
`list_scheduled` line writes it (`relative_day` in `schedule_render.py`), such as `due
2026-10-25T09:00:00+01:00 (tomorrow)`. The day is counted in the zone the time is rendered in, so
under the UTC default it is the UTC day, which is the person's day only when the display zone is
theirs, as the stack recipes now make it ([ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md)
decision 5).

**Driver** (`slot9/draw.py`): T5's driver, which also marks a draw whose reply names a day other
than the stored one: "today" or "tonight" without "tomorrow" over an item due tomorrow, or
"tomorrow" without "today" or "tonight" over one due today, both counted in the display zone.

**Rows, written before the baseline:** T4's **A** and **F** at 2026-10-24 23:50 CEST in Berlin
(due tomorrow) and **E** at 03:00 under the UTC zone (due today), 10 draws each, on the baseline
(HEAD) and on the candidate.

**Rule:** the candidate ships only if its count of wrong-day replies over the 30 draws is below
the baseline's, and no candidate draw ends with a past, wrong or duplicated item (T5's classes).
A baseline count of 0 cannot fall: then the task stays open with these rows as its evidence.

### T6 results

SM clock during the draws: 0.59 of `clocks.max.sm`. "Wrong day" counts replies that name a day
other than the stored one; the store classes are T5's.

| Row | Baseline wrong day | Candidate wrong day | Candidate store |
| --- | --- | --- | --- |
| A | 0 of 10 | 0 of 10 | 10 wanted, one call |
| F | **7 of 10** | **2 of 10** | 7 wanted, 2 daily rules due tomorrow, 1 asked |
| E | 0 of 10 | 0 of 10 | 7 wanted, 3 named daily rules, as in the baseline |

- **The candidate passes its rule and shipped**: 2 wrong-day replies in 30 against 7, and no draw
  ended with a past, wrong or duplicated item. In F the baseline echoed the person's "today" in 7
  replies; with `(tomorrow)` in the result, 7 of the 9 stored draws said "tomorrow".
- One of the candidate's two is a counting artifact: "Since you only asked for today, I can change
  it" over a daily rule, which names "today" without saying the item is due then. The other
  replied "today at 9:00 AM" over a daily rule due tomorrow.
- The day is counted in the display zone, so under the UTC default it is the UTC day. With the
  host's zone passed by the stack recipes it is the person's day. The core suite
  (`brain/packages/core/tests`) holds a test that fails when the day is counted in UTC.
