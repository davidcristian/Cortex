# Readings: tool runs in a recalled exchange

What the cortex does when recall shows it an earlier chat's request and reply for the same
request: whether it makes the call again or copies the reply. No decision rests on these readings
yet; they were taken for
[R-836](../refinements/tasks/836-a-recalled-exchange-is-claimed-again-with-no-call.md), next to
the replay of a chat's own runs in [ADR-0074](../adr/ADR-0074-replayed-tool-runs.md).

## The rig

**2026-10-11**, the GPU stack with the resident cortex (gemma-4-12B), both CPU subagent servers,
the filesystem sidecar and the pgvector memory override, as in
[overlay-file-and-memory-flows.md](overlay-file-and-memory-flows.md#the-rig), under its own compose
project with fresh volumes, so no row from an earlier night is in memory. The brain runs with
`CORTEX_SCHEDULE_BACKEND=redis`, `CORTEX_SCHEDULE_TZ=UTC` and `CORTEX_MEMORY_RECALL_AUDIT=1`, and
every other memory setting at its default. Each repeat goes over `Converse` from a driver inside
the brain container, one fresh chat per repeat. The driver prints each turn's tool runs and reply,
and joins the `cortex.memory.recall` line's hits to the rows in `memories`; it is `slot3/drive.py`
with `run.sh` and `report.py` beside it, in the run's scratch directory.

## Rows and the rule, written before the first run

The change measured, T: the exchange recorded at turn end names the turn's tool runs on a line
between the user's message and the reply, and the header of the recalled block says that a run it
lists ran in that earlier chat only, so a request made now needs its own call.

Every row asks "Remind me tomorrow at 10:00 to check whether the bulb order went out." in each of
five fresh chats, one after the other, and keeps the memory rows each chat writes, so a later chat
recalls the earlier ones. A turn counts as a **false claim** when its reply says a reminder was
set and the turn made no `schedule_task` call.

| Row | Build | Memory at the start | Repeats |
| --- | --- | --- | --- |
| R1 | HEAD | empty | 5 |
| R2 | T | empty | 5 |
| R3 | T | the five rows R1 wrote, in the format before T | 5 |
| Q | T | the rows R2 wrote | 2, asking "Did I ask you to set any reminders about the bulb order?" |

R3 is an existing store: its rows were written before the change and name no runs. Q checks that
a recalled run is not repeated when the person only asks about it.

**Pass rule.** T ships only if R1 reproduces the defect, with at least 2 of its 5 turns a false
claim; R2 has no false claim; and neither Q chat makes a `schedule_task` call. If R1 has fewer than
2 false claims the result is null: T is not shipped and the task stays open. R3 does not decide
whether T ships; if it has 2 or more false claims, the rows written before T are filed as their
own task.

**Replication, written after R1 and before any run of it.** R1 had no false claim. Two more rows
run on HEAD before any decision. R1b is ten more fresh chats with the same request, keeping R1's
rows, so each recalls five or more earlier exchanges. R1c is five fresh chats asking "Can you
remind me at 10:00 tomorrow to check on the bulb order?", keeping every earlier row, so the
recalled request is worded differently from the one asked. If R1b has at least 2 false claims of
10, or R1c at least 2 of 5, the defect reproduces: R2 and R3 then run that row's shape under T as
well, and the pass rule above applies to it. If neither does, the result is null.

## Results

**2026-10-11**, on HEAD, before any change. SM clock during the rows: 0.58 to 0.59 of
`clocks.max.sm`. Each cell counts chats.

| Row | Chats | `schedule_task` called and stored | False claims | Recalled earlier rows |
| --- | --- | --- | --- | --- |
| R1 | 5 | 5 | 0 | 0, then 1 to 4 |
| R1b | 10 | 9 | 1 | 5 (the recall `k`) |
| R1c | 5 | 4 | 1 | 5 |

The result is null under the rule above, so T was not built and R2, R3 and Q did not run. No turn
of the 20 made no call at all, the shape the task was filed from: 18 called `schedule_task` and
stored a reminder before replying. Both false claims are another shape. Each turn called only `list_scheduled`, whose result listed the same reminder, stored by
the earlier chats, and replied "OK. I've set a reminder for you tomorrow, October 12th, at
10:00 AM ...", the same text as the replies that did store one
([R-839](../refinements/tasks/839-a-reply-says-it-set-a-reminder-it-only-found-listed.md)).

The rows filed in R-836 ran on 2026-10-10 under the earlier text of `schedule_task`'s `at` and
`at_time` arguments ([schedule-one-time-and-daily.md](schedule-one-time-and-daily.md#results));
the rows after that change deleted memory before each chat, so they did not test recall.
