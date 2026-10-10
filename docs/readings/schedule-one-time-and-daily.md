# Readings: one-time and daily times in schedule_task

Whether the cortex stores a request for one time ("tomorrow at 10:00") as a one-shot, through
`at`, or as a daily item, through the recurring `at_time` argument, and whether a request that
repeats still gets a rule. Read with [ADR-0025](../adr/ADR-0025-scheduling-reminders.md); the
tool is `brain/packages/core/src/cortex_core/schedule_tools.py`.

## The rig

**2026-10-10**, the GPU stack with the resident cortex (gemma-4-12B), both CPU subagent servers,
the filesystem sidecar and the pgvector memory override, as in
[overlay-file-and-memory-flows.md](overlay-file-and-memory-flows.md#the-rig), with
`CORTEX_SCHEDULE_BACKEND=redis` and `CORTEX_SCHEDULE_TZ=UTC`. Each row goes over `Converse` from a
driver inside the brain container, one fresh chat per repeat, and the stored item is read back
from Redis by its `session_id`. The driver is `slot17/drive.py` in the run's scratch directory.

## Rows and the rule, written before the first run

| Row | Request | Repeats | Stored as wanted |
| --- | --- | --- | --- |
| A | "Remind me tomorrow at 10:00 to check whether the bulb order went out." | 5 | one-shot, no `rule` |
| B | "Set a reminder for 10:00 tomorrow morning to water the plants." | 2 | one-shot, no `rule` |
| C | three turns: the file question, a reminder for tomorrow at 9:00, then the file read and a task for tomorrow at 10:00 | 5 | every reminder one-shot |
| D | "Remind me every day at 10:00 to take my vitamins." | 2 | a daily `rule` |
| E | "Remind me every Monday at 9:00 to send the weekly report." | 2 | a `rule` on Monday |

Row C is the shape the defect was found in: the task call is refused on the tainted turn, and the
reminder made after it was the one stored with a daily rule. A null result is a baseline with no
`rule` item in A, B or C, which would leave the description alone and the defect unreproduced.

**Pass rule for a change to the `at` or `at_time` text:** it ships only if, after the change, no
item from rows A, B and C is stored with a `rule`, every item from rows D and E is, and no reply in
A or B names a day other than the stored `due_at`.

**Second condition, written after the first baseline and before any run under it.** In the first
baseline, recall returned earlier repeats' exchanges and later repeats made no call at all
([R-836](../refinements/tasks/836-a-recalled-exchange-is-claimed-again-with-no-call.md)), so a
row stopped measuring the argument. Under the second condition the memory rows this run wrote are
deleted before each chat, so every repeat recalls what the first one did. The pass rule applies
to the second condition, before and after the change, and also fails if any repeat of rows A, B,
D or E in it makes no call. Row C keeps the earlier slot's memory rows, as when the defect was
found.

**Row F, written after the first baseline and before any run of it.** The calls that passed
`at_time` for one time were logged with `CORTEX_MEMORY_ON_TAINTED=record`, where recall returns
tainted rows. Row F recreates that: the brain with recording on, two chains of row C to store
tainted rows, then five fresh chats asking "Schedule a background task for tomorrow at 10:00 that
checks whether the garden club bulb order went out. Do not open any file." It counts the
`schedule_task` calls whose audited arguments hold `at_time`. The same pass rule applies: no
`at_time` call for a one-time request after the change, with rows D and E still stored with a
`rule`.

## Results

Row C was enough to reproduce the defect without recording, so row F was not run. Each cell counts
chats; "rule" is an item stored with a `rule`, and "no call" is a turn that made no
`schedule_task` call. SM clock during the rows: 0.58 to 0.67 of `clocks.max.sm`.

| Run | Text | A | B | C, turn 2 | D | E |
| --- | --- | --- | --- | --- | --- | --- |
| first baseline | shipped | 2 `at`, 3 no call | 2 `at` | 1 rule of 5 | 1 rule, 1 no call | 2 rule |
| second condition | shipped | 5 `at` | 2 `at` | not valid | 2 rule | 2 `at_time`, not stored |
| second condition | changed | 5 `at` | 2 `at` | 5 `at`, 0 rule | 2 rule | 2 rule |

The change passed its rule: no item for one time had a `rule`, both repeats were stored with one,
every A and B reply named the stored day, and every A, B, D and E repeat made its call. Its items
were deleted before the next chat, so this row reads the stored shape from each call's audited
arguments and `ok=True`. In its third turns, two chains made no call and claimed the task, as in
the first baseline ([R-834](../refinements/tasks/834-a-reply-claims-a-task-it-never-tried-to-schedule.md)).

- **The defect.** In the first baseline, the fifth chain's second turn, "Set a reminder for
  tomorrow at 9:00 to call Ana about the bulb payments.", made two calls: `at_time: "09:00"` with
  `in_zone: "UTC"`, stored daily and first due at 09:00 UTC the same day, and `at` for the next
  day. The reply said "tomorrow, October 11th, at 9:00 AM". In the third turns, three task calls
  were refused (all with `at`) and two turns made no call and claimed the task.
- **No call.** The three A repeats and the D repeat that made no call each recalled the earlier
  repeats' exchanges and copied their reply
  ([R-836](../refinements/tasks/836-a-recalled-exchange-is-claimed-again-with-no-call.md)).
- **Not valid.** The second condition filled the schedule to `CORTEX_SCHEDULE_MAX_ACTIVE` (32)
  from row E on, so E's calls were refused as full and row C measured nothing. The run after the
  change deleted this run's schedule items before each chat as well.
