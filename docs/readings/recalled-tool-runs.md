# Readings: tool runs in a recalled exchange

What the cortex does when recall shows it an earlier chat's request and reply for the same
request: whether it makes the call again or copies the reply. They were taken for
[R-836](../refinements/tasks/836-a-recalled-exchange-is-claimed-again-with-no-call.md), and the
rows of the last section decide decision 6 of
[ADR-0074](../adr/ADR-0074-replayed-tool-runs.md), beside the replay of a chat's own runs.

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
stored a reminder before replying. Both false claims are another shape. Each turn called only
`list_scheduled`, whose result listed the same reminder, stored by the earlier chats, and replied
"OK. I've set a reminder for you tomorrow, October 12th, at 10:00 AM ...", the same text as the
replies that did store one ([reminder-already-stored.md](reminder-already-stored.md)).

The rows filed in R-836 ran on 2026-10-10 under the earlier text of `schedule_task`'s `at` and
`at_time` arguments ([schedule-one-time-and-daily.md](schedule-one-time-and-daily.md#results));
the rows after that change deleted memory before each chat, so they did not test recall.

## Drawn over a stored reminder, written 2026-10-12 before any run of it

The false claims of
[reminder-already-stored.md](reminder-already-stored.md#results-on-the-new-store) come from recall:
4 of 50 chats in B2, none of 50 with memory empty (row M). This section draws T over that shape,
with T as written above. A memory row's text is fixed when the row is written, so a row stored
before T renders as before under T, and T drawn over B2's store would test only its header.

**The store.** T3, E3 and Q3 run over B2's starting set (8 reminders due 2026-10-13T10:00Z and the
20 exchanges written by the seeding chats `r839-s2a-r1` to `r839-s2a-r15` and `r839-s2c-r1` to
`r839-s2c-r5`), with each of the 20 memory rows rewritten in place. Its new text is the treated
tree's `render_exchange` over the row's own message and reply and the runs the driver recorded for
that seeding chat's turn, which are the `ToolOutcome` events `RunLog` collects. Its new embedding
is the brain's `LlamaCppEmbedder` over `embedding_input` of that text, the record path's own
steps. Id, scope, taint and `created_at` stay. Rows are matched to chats in `created_at` order and
each match is checked on the message. Before the rewrite, re-embedding each row's current text
must give its stored vector back (cosine at least 0.9999), or the procedure is not the record
path and no row runs. After the rows, B2's rows are reloaded from their dump.

This is the store T would have written had the same 20 seeding chats run under it, and it keeps
the reminders and every reply the same, so the run lines are the one difference from B2's store
and B2 stays the baseline. It does not measure how the seeding chats themselves behave under T.
A store seeded by new chats under T would differ from B2's in its items and replies as well (the
first seed stored 18 reminders, the second 8), so a difference between the rows would not be T's
alone.

| Row | Build | Request | Chats |
| --- | --- | --- | --- |
| T3 | T | B2's two requests, alternating | 50 |
| E3 | T | "Remind me tomorrow at 11:00 to call the plumber." | 6 |
| Q3 | T | "What reminders do I have about the bulb order?" | 5 |

The driver and false claim are those of
[reminder-already-stored.md](reminder-already-stored.md#rows-and-the-rule-written-before-the-first-run):
every chat is fresh over the same store, and a false claim is a turn with no successful
`schedule_task` call whose reply says a reminder was set. B2 found 4 of 50 on this store today,
and B, T, B2 and T2 together 18 of 200, since neither result text moved the turn's first step. If
T changes nothing, 50 chats with no false claim has probability 0.92^50 = 0.015 at B2's rate.

**Pass rule.** T ships only if T3 has no false claim, every E3 chat stores exactly one one-shot
due 2026-10-13T11:00Z, and no Q3 chat calls `schedule_task`. Otherwise T is not shipped, and the
replies of any false claim are quoted here. The rows run before 00:00Z on 2026-10-13, while
"tomorrow at 10:00" is still the stored reminders' due time.

## Results over the stored reminder

**2026-10-12**, on T, with the driver of
[reminder-already-stored.md](reminder-already-stored.md#results-on-the-new-store). SM clock during
the rows: 0.58 to 0.69 of `clocks.max.sm`. Each cell counts chats.

Re-embedding each of the 20 rows' current text gave its stored vector back, at a worst cosine of
1.000000, so the rewrite used the record path. Every row matched its seeding chat's message and
reply. The rewritten rows hold the runs those chats made: `schedule_task` in 13, `list_scheduled`
alone in 4 (the seeding chats that claimed a reminder), `list_scheduled` then `schedule_task` in
2, and in the eleventh `list_scheduled` then seven `cancel_scheduled` calls.

| Row | Chats | `schedule_task` called | Items stored | False claims (odd, even) |
| --- | --- | --- | --- | --- |
| B2, HEAD, the same store before the rewrite | 50 | 46 | 46 | 4 (1, 3) |
| T3 | 50 | 50 | 50 | 0 |
| E3 | 6 | 6 | 6 | 0 |
| Q3 | 5 | 0 | 0 | 0 |

T passed its rule, and it ships. 47 T3 chats called only `schedule_task`, and the other 3 called
`list_scheduled` first and then `schedule_task`, against 9 B2 chats that listed, of which 5 went
on to call. Every E3 chat stored one one-shot due 2026-10-13T11:00Z, and every Q3 chat called only
`list_scheduled` and replied with the stored reminders.

The rewrite changed the rows' embeddings, so recall chose among them differently: one or more of
the 4 list-only exchanges was among a chat's 5 hits in 25 of B2's chats and in 14 of T3's. In B2,
3 of the 4 list-only turns were in chats that recalled one. In T3, none of the 14 chats that
recalled one ended without a `schedule_task` call. The chat logs and recall lines are in
`runs/r839-t3*` and `runs/r839-b2*` in the run's scratch directory.
