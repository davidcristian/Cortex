# Readings: a refused `spawn_subagents` on a request to remember and remind

On a message that asks to remember a fact and to set a reminder, the cortex sometimes calls
`spawn_subagents` with one instruction per request. On such a turn `unasked_sidecar_tools` refuses
the call, since the subagents hold the MCP tools and a file they read would taint the turn and
lose the fact ([ADR-0013](../adr/ADR-0013-untrusted-content.md) decision 5). A subagent holds no
`schedule_task` and no memory tool, so the spawn could not have set the reminder; what matters is
what the cortex does after the refusal. The rows of 2026-11-10 that found it are in
[overlay-compound-request-flows.md](overlay-compound-request-flows.md#counts).

## Rows and the rule, 2026-11-10

Written before any build was drawn. The rig is the `cortexn18` stack over `Converse`: the cortex
gemma-4-12B at context 16,384, llama.cpp build `12182`, Redis schedules with
`CORTEX_SCHEDULE_TZ=Europe/Berlin`, the Linux shell as the body, the filesystem sidecar, every card
approved, a new chat for each draw, and every row and schedule item deleted before each draw.

| Row | Message | Pool at the draw's start |
| --- | --- | --- |
| M1 | `Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h de vider le casier.` | empty |
| M2 | `Vergiss meinen alten Spindcode 4417, merk dir, dass der neue 5528 ist, und erinnere mich am Freitag daran, ihn zu testen.` | one row from a real turn of `Merk dir, dass mein Spindcode 4417 ist.`, copied back before each draw |
| M3 | `Remember that my locker code is 4417 and remind me at 18:00 to empty the locker.` | empty |

Three builds, each a brain beside the stack with its model calls through its own recording proxy:

- **Base**: a `git archive` build of `6188ea5b3`, which refuses the call with `UNASKED_MSG`.
- **A**: the same with `SPAWN_UNASKED_MSG` as the refused spawn's result. It says that no subtask
  ran, that a subagent cannot keep a fact or set a reminder, and to call the matching listed tool
  for each thing the person asked for, such as `schedule_task`, or to say it was not done. It names
  no forget.
- **B**: the base with `spawn_subagents` left out of the tool list on a turn where
  `unasked_sidecar_tools` refuses it. A call to it by name is still refused.

Each row is drawn 4 times on each build, in rounds of M1, M2, M3, the build order turning by
round. **The form** is a draw with a refused `spawn_subagents`, read from the brain's
`tool.invocation` audit lines; its count per build is reported on its own. **Continuation replays**
measure the form directly: each recorded request whose last message is a refused spawn's result
is sent straight to the cortex server 4 times with `UNASKED_MSG` in that result and 4 times with
`SPAWN_UNASKED_MSG`, at the recorded settings, the text that goes first turning by draw. If no
draw records one, a request is built from each message's recorded first request and a spawn call
of the form the brain audit recorded on 2026-11-10 for `Remember that I park on level 3 and remind
me tomorrow at 9 to move the car.` A continuation is read as a `schedule_task` call, a text saying
the reminder was not set, a claim that it was set with no call, or none of these.

A ships when all of these hold:

1. Summed over the replayed requests, A's text is followed by a `schedule_task` call in at least 2
   more replays than the base text, and by a claim with no call in no more.
2. No continuation after A's text calls `spawn_subagents` again, or `forget_memories` on M1 or M3.
3. In the draws, M1 and M3 call `forget_memories` in no more A draws than base draws plus one, and
   every asked reminder is stored, or the reply or a brain note says it was not, in no fewer A draws
   than base draws.
4. No draw on any build runs `spawn_subagents` or a file tool, and M1 and M3 store the fact row in
   no fewer A draws than base draws less one.
5. A request to remember with no reminder asked, `Mein Fahrradschloss hat den Code 2468, merk dir
   das.`, has two recorded requests after a refused spawn (proxy logs of 2026-11-09 and 2026-11-10).
   Each is replayed 2 times per text: A's text is followed by a call to `forget_memories`,
   `schedule_task` or `set_volume` in no more replays than the base text. Added before these
   replays were drawn, after the first draws.

B ships, when A does not, if the asked reminder is stored by a call in at least 2 more of the 12 B
draws than of the 12 base draws, with items 3 and 4 read for B.

The null result: neither ships. Then the refusal's text is not what drops a reminder, and the task
stays open with these rows if a base draw or replay dropped one with no reply or note saying so,
and is declined if none did.

## The draws, 2026-11-10

36 draws from 05:25 to 05:42 local time, SM clock 0.57 to 0.71 of `clocks.max.sm`, and 32
continuation replays beside them. Run logs `rows-base.jsonl`, `rows-a.jsonl`, `rows-b.jsonl`,
`replay-built.jsonl`, `replay-rem.jsonl` and the counts `count.txt` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot13/`.
No draw ended in an error. Each brain was checked before the draws: only A holds
`SPAWN_UNASKED_MSG`, and only B leaves the spawn out of the list.

| Count | Base | A | B |
| --- | --- | --- | --- |
| Draws with a refused spawn (the form) | 3 of 12 | 2 of 12 | 0 of 12 |
| Asked reminder stored by a call | 12 of 12 | 12 of 12 | 12 of 12 |
| Of those, after a refused spawn | 3 of 3 | 2 of 2 | none |
| M1 and M3 calling `forget_memories` | 0 of 8 | 1 of 8 (refused) | 2 of 8 (1 ran, matched nothing) |
| M1 and M3 storing the fact row | 8 of 8 | 8 of 8 | 8 of 8 |
| Draws running `spawn_subagents` or a file tool | 0 | 0 | 0 |

No draw recorded a request after a refused spawn on M1 to M3 through its build's proxy in time
for the replays, so they used the three built requests:

| Replayed request | `schedule_task` after the base text | after A's text |
| --- | --- | --- |
| M1 | 4 of 4 | 4 of 4 |
| M2 (the forget not yet run) | 2 of 4, beside `forget_memories` | 0 of 4, `forget_memories` alone |
| M3 | 4 of 4 | 4 of 4 |
| `Mein Fahrradschloss ...`, a call to `forget_memories`, `schedule_task` or `set_volume` | 0 of 4 | 0 of 4 |

Every built continuation was a tool call, so none claimed a reminder. After the base text one
continuation of the remember-only request called `spawn_subagents` again, against none after A's.

**Item 1 fails for A** (8 replays against 10), and B stores no more reminders than the base, so
**this is the null result** and neither ships. Every base draw and replay after a refused spawn
went on to store the reminder, so the refusal's text does not drop it on this build. The one
drop on record, c6 of the compound flows, was a false claim with no call, which
`UNSCHEDULED_CLAIM_NOTE` now shows ([claim](overlay-compound-request-flows.md#the-french-claim-with-an-object-pronoun)).
Two stored draws replied that the fact was not saved: A's M3 after a refused forget (`I noticed I
didn't save it`) and B's M1 after a forget that matched nothing (`je n'ai pas pu m'en souvenir`),
the reply [R-1001](../refinements/tasks/1001-a-request-to-remember-with-a-reminder-says-the-fact-was-not-saved.md)
waits for.
