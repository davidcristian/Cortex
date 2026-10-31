# Readings: tools with a side effect called on a request to remember

How often a request to remember a fact makes the cortex call `set_volume` or `schedule_task`,
two tools that show no card, and whether a request that also asks for a reminder or a volume
change still calls them. Tonight's draws before this record found 3 `set_volume` calls in 88
requests to remember and 2 `schedule_task` calls in 32, one of which stored a yearly reminder
nobody asked for ([forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)).

## Rows and the rule, 2026-10-30

Written before the baseline was drawn. The rig is the `cortexn11` stack over `Converse` (the
cortex gemma-4-12B at context 16,384, schedules on, the Linux shell as the body), a new chat
for each draw, every card approved, `memories` empty at each draw's start. After each draw every
`memories` row it wrote is deleted, and every schedule it added is cancelled with
`RedisScheduleStore.cancel`.

| Row | Message | Draws | Tool asked for |
| --- | --- | --- | --- |
| R01 to R15 | the requests to remember of [forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-rows-and-rule-2026-10-30), each its own row | 2 each | none |
| A01 | `Please remember this: I take my pills at 8 pm. Remind me every day at 8 pm to take them.` | 2 | `schedule_task` |
| A02 | `Note that my mother's birthday is on 12 May, and remind me of it the day before.` | 2 | `schedule_task` |
| A03 | `Remember to call the plumber tomorrow at 10.` | 2 | `schedule_task` |
| A04 | `Please remember this: I like my music quiet, so turn the volume down to 20%.` | 2 | `set_volume` |
| A05 | `Keep in mind that I am in a meeting now, so please mute the sound.` | 2 | `set_volume` |
| A06 | `Please remember this: I am hard of hearing. Set the volume to 80%.` | 2 | `set_volume` |

`asks_kept` (`memory_request.py`) reads every row above as a request to remember.

- An R draw fails when its turn calls `set_volume`, `get_volume` or `schedule_task`, read from a
  `ToolActivity` event or a card naming it. An A draw passes when its turn calls the tool its row
  asks for, whether or not the call succeeds; the Linux shell's volume call fails.
- The candidate leaves `set_volume` out of the tool list of a turn whose message `asks_kept`
  reads, unless the message names the sound, and `schedule_task` unless it asks for a reminder,
  and refuses a call to either by name on such a turn.
- The candidate ships when R01 to R15 fail in 0 of 30 draws, A01 to A06 pass in no fewer draws
  than the baseline's count less two, every A row that passes in a baseline draw passes in a
  candidate draw, and R01 to R15 store the fact in no fewer draws than the baseline's count less
  three.
- The baseline is every row with the shipped build. A baseline whose R draws call none of the
  three tools leaves tonight's 5 recorded calls as the defect's evidence; it then decides the A
  rows and the stored facts only. The null result is a candidate that fails any part of the
  rule: it is reverted and both tasks stay open.

## Baseline, 2026-10-30

Run log `base.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot7/`,
the shipped build, the SM clock at 0.60 of its maximum at the start and 0.59 at the end.

| Rows | Result | What the draws did |
| --- | --- | --- |
| R01 to R15 | 2 of 30 fail | "my car is a red Fiat" called `set_volume` and `schedule_task`, both failed, and the reply said only that the car was noted; "my daughter is allergic to peanuts" called `set_volume` and `list_allowed_directories` |
| R01 to R15 | 29 of 30 store the fact | the peanuts draw stored nothing, since the file tool's result tainted the turn ([R-950](../refinements/tasks/950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md)) |
| A01 to A06 | 12 of 12 pass | each A01 to A03 draw stored its reminder; each A04 to A06 volume call failed and the reply said so; one A06 draw also called `schedule_task` |

The baseline is not the null result: 2 of 30 R draws called a tool with a side effect, beside the
5 recorded earlier tonight.

## The candidate, 2026-10-30

The candidate is the change the rule describes: `unasked_tools` (`unasked_tools.py`) fills the
loop's `LoopRecord.unasked`, the tool loop leaves those tools out of the list, and a call to
one by name is refused as `UNASKED`. Run log `cand.jsonl` beside `base.jsonl`, the SM clock at
0.59 of its maximum at the start and 0.60 at the end. R01, R02 and A03 to A06 were drawn from
04:30 and the other rows from 04:35; a driver import failure between them drew nothing.

| Rows | Baseline | Candidate |
| --- | --- | --- |
| R01 to R15 failing | 2 of 30 | 0 of 30 |
| R01 to R15 storing the fact | 29 of 30 | 30 of 30 |
| A01 to A06 passing | 12 of 12 | 12 of 12, each row 2 of 2 |

The change ships: no R draw called a tool with a side effect, every A row called its tool in both
draws, and every R draw stored its fact. Two more observations:

- 12 of the 30 candidate R draws called `forget_memories`, against 5 of 30 in the baseline. Each
  matched nothing and the fact was kept ([forget-no-match-on-remember.md](forget-no-match-on-remember.md)).
  It is one row's surprise and decides nothing here.
- One A02 draw stored a reminder on the 11th of every month, and its reply said so; the other
  stored it yearly on 11 May
  ([R-951](../refinements/tasks/951-a-reminder-the-day-before-a-yearly-date-can-repeat-monthly.md)).

## The forget calls on a request to remember: replication rows and rule, 2026-10-30

Written before it was drawn, to check the candidate's 12 of 30 R draws calling `forget_memories`
against the baseline's 5 of 30. The rig is the one above, on the shipped candidate build.

| Row | Message | Draws |
| --- | --- | --- |
| R01 to R15 | as above, each its own row | 2 each |

- A draw counts when its turn calls `forget_memories`, read from a `ToolActivity` event or a card.
- The rise **replicates** when at least 10 of the 30 draws count. A separated pair is then filed
  as a task: the build before the change and the build after it, drawn in turn, so a run's drift
  cannot pass for the change's effect.
- It **does not replicate** when at most 7 of 30 count. The candidate's 12 is then one run's
  surprise and nothing is filed.
- 8 or 9 of 30 is no result: the separated pair is filed as a task.
- No behaviour changes on this row in any case.

## The forget calls on a request to remember: replication, 2026-10-30

Run log `rep.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot8/`,
the shipped candidate build, the SM clock at 0.63 of its maximum at the start and 0.60 at the end.
8 of the 30 draws called `forget_memories` (R03 and R08 twice, R01, R06, R09 and R15 once), every
draw stored its fact, and none called a tool with a side effect. 8 of 30 is no result, so the
separated pair is filed
([R-952](../refinements/tasks/952-withheld-unasked-tools-may-raise-forget-calls-on-a-remember-request.md)).

## The forget calls on a request to remember: separated pair, rows and rule, 2026-10-31

Written before either build was drawn. The pair decides whether leaving `set_volume` and
`schedule_task` out of the tool list raised the forget calls, or whether the counts of 5, 12 and 8
of 30 above were drift between runs.

The rig is the `cortexn12` stack over `Converse`: the cortex gemma-4-12B at context 16,384,
llama-server build `b12004-3c809f443`, schedules on, the Linux shell as the body, a new chat for
each draw, every card approved, `memories` empty at each draw's start. Two brain containers run
beside each other against that stack's model server and stores. "Before" is a `git archive` build
of `6b9956582`, the commit before the change, and "after" is one of `86ce47177`, the change. Each
image's `cortex_core` is compared with its archive before any draw.

| Row | Message | Draws |
| --- | --- | --- |
| R01 to R15 | as above, each its own row | 2 each on each build, 60 in all |

The builds are drawn in turn. One draw of a row on one build is followed at once by a draw of that
row on the other, and the build that goes first alternates by row and by pass. A draw that ends in
an error is not counted and is drawn again at the end of its pass.

- A draw counts when its turn calls `forget_memories`, read from a `ToolActivity` event or a card.
  D is the after count less the before count.
- **The change raised them** when D is at least 7. That is the rise that raised the question (5 to
  12), and about twice the spread of D when both builds call near 8 of 30.
- **The earlier counts were drift** when D is at most 3.
- D of 4 to 6 is no result. A second pair of the same size is then drawn the same way and read over
  all 120 draws: the change raised them when D is at least 10, and the counts were drift otherwise.
- The pair cannot see a rise much smaller than these bounds, so a null result rules out a rise of
  that size and not a smaller one.
- No behaviour changes on this pair in any case. A rise leaves the withheld tools in place, since
  they shipped on their own rule and every calling draw kept its fact, and files a task whose first
  step is rows and a rule for any change to the forget calls. A null result closes the question
  and files nothing.

## The forget calls on a request to remember: separated pair, the draws, 2026-10-31

Run log `pair.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot2/`.
Each image's brain packages matched its archive file for file, and the two differ only in the
change. The SM clock read 0.21 to 0.22 of its maximum just after each draw, on a card back near
idle. No draw ended in an error and `memories` was empty at every draw's start.

| Build | Calling `forget_memories` | Storing the fact | With a forget card | Other tools shown |
| --- | --- | --- | --- | --- |
| Before | 1 of 30 | 30 of 30 | 0 | one `schedule_task` |
| After | 13 of 30 | 30 of 30 | 0 | none |

D is 12, so by the rule **the change raised the forget calls**, and the earlier counts were not
drift. A later run did not repeat the size of this result
([readings](unasked-tools-listed-on-remember.md#the-draws-2026-10-31)). The rise held in both passes (0 against 5, then 1 against 8) and in both orders (1 against 5
when the build was drawn first, 0 against 8 when second). Before called only on R09. After called
on R01, R02 and R12 twice, and on R05, R07, R09, R10, R11, R14 and R15 once.

The rule leaves the withheld tools in place. Three things the pair does not settle:

- Before's 1 of 30 is below the 5 of 30 this brain code drew on 2026-10-30, on an older
  llama-server build. Both builds of the pair ran on one server, so the comparison stands; the
  absolute rate between nights does not.
- It does not say which of the two tools moves the count. With schedules off altogether, 9 of 56
  draws called it on 2026-10-30 ([readings](forget-card-on-remember.md#more-forget-calls-with-schedules-on-the-separation-2026-10-30)).
- Every draw started from an empty pool. Each of the 14 calls matched nothing, so `card`
  (`memory_forget_chosen.py`) returned `None` and no card was shown; the same held for all 25
  calls of the three 2026-10-30 runs. A pool holding the text would show a card, which no row has
  drawn since the change.

## Near misses for the reader's new verbs, checked 2026-10-30

Unit runs of `asks_kept`, `asks_not_kept` and `unasked_tools` over hand written messages, after
"erase", "unlearn", "get rid of", "stop remembering", "drop it" and "note" joined the request
reader. `asks_not_kept` is read only by `memory_withheld`, whose result decides whether the turn
is recorded and whether a reply claiming something was noted gets `UNKEPT_CLAIM_NOTE`.
`unasked_tools` reads only `asks_kept` and leaves out only `set_volume` and `schedule_task`, so a
file request read as not to keep keeps its file tools. Its turn is not recorded; the file itself,
the chat and the tool audit still hold what was done.

| Message | Reading when checked | Result |
| --- | --- | --- |
| "Note down the meeting time and remind me at 4" | kept, `schedule_task` offered | checked |
| "Erase the whiteboard photo from my notes and remember the new layout" | not kept, as "forget X and remember Y" | checked |
| "Stop remembering my old address, my new one is Hauptstr 5" | not kept, as "forget X" beside a new fact | checked |
| "Drop it in my calendar" | neither | checked |
| "Get rid of the typo and save the draft" | neither | checked |
| "Note my dentist appointment Friday at 3 and give me a heads-up an hour before" | kept, `schedule_task` left out | fixed, now offered |
| "Note my flight at 6 and text me at 4" (also nudge, buzz, warn, message, poke me) | kept, `schedule_task` left out | fixed, now offered |
| "Note my code 7319 and turn it down" | kept, `set_volume` left out | fixed, now offered |

The fixed rows held for "remember" before "note" joined, so the reminder and sound words of
`unasked_tools.py` now include "heads up", those six "... me" forms and "turn it, this or that up
or down". A word read wrongly only keeps a tool offered, which is the behaviour of any message
that asks nothing to be remembered.
