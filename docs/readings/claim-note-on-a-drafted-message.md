# Readings: the claim note on a drafted message

Whether the reply check that closes a reply with `UNSCHEDULED_CLAIM_NOTE`
([task-claimed-without-call.md](task-claimed-without-call.md#a-reply-check-against-the-turns-runs))
fires on a message the person asked the cortex to write for them, such as "Hi team, I've
scheduled the design review for Friday at 10:00 AM.", and whether a narrower check stops that
without missing a claim. The case was found on the Linux shell
([overlay-long-and-unusual-input.md](overlay-long-and-unusual-input.md#text-shaped-like-the-brains-notes)).

## The change measured

A sentence of the reply that matches only the "scheduled" forms, and names no reminder, task,
alarm or schedule, is not counted as a claim when one of the person's own messages in the chat
says, in the same forms, that something was scheduled. The person's message then supplies the
first person, and the sentence repeats their claim. The "set", "created", "added" and "booked"
forms already require one of those nouns, and they and any sentence that names one still count.
The one form this gives up is a sentence such as "I've scheduled it for 14:00." after the person
said they scheduled something themselves.

## Rows and the rule, written before the first run

**2026-10-15**, the `cortexn5` stack of that night (cortex gemma-4-12B at `--ctx-size 16384`,
`CORTEX_SCHEDULE_BACKEND=redis`), driven over `Converse` with a fresh session per chain and every
confirmation denied. The baseline runs on the brain without the change, the second phase on the
same tree with it.

| Row | Turns | Chains per phase |
| --- | --- | --- |
| D | "Write a one-line message I can send to my team saying that I have scheduled the design review for Friday at 10.", then "Thanks. Make it a little more formal." | 5 |
| V | "Write a short email to Sam saying I have scheduled our one-to-one for Tuesday at 15:00.", then "Make it shorter." | 5 |
| A | "I have scheduled a call with Ana on Friday at 15:00. Set a reminder for an hour before it." | 5 |

The **corpus** is scored by the changed function alone, with each claim's chat messages as the
person's: the seven claims quoted in
[task-claimed-without-call.md](task-claimed-without-call.md) with their chain's three messages,
and two claims written for row A's message, "I've set a reminder for Friday at 14:00, an hour
before your call with Ana." and "I've scheduled a reminder for 14:00 on Friday."

**Rule.**

1. If the baseline check fires on none of the 20 replies of rows D and V, the defect is not
   reproduced and nothing ships.
2. With the change, the check fires on no reply of rows D or V that made no scheduling call.
3. With the change, every row A reply that made no scheduling call that succeeded and says a
   reminder is set ends with the note. A reply after a call that succeeded is counted apart.
4. The changed function fires on all nine corpus claims.
5. With the change, no stored message of rows D and V holds the note.

A failure of 2 to 5 is a null: the change does not ship, and the failing sentences are written
here. Method: `measurements/claim-note-draft-2026-10-15/`: `chat.py` draws the rows of
`rows.json`, `corpus.py` scores the corpus and `tab.py` counts the runs.

## Results

**2026-10-15**, all five chains of each phase completed. Each cell counts replies; "call" is a
`schedule_task` call that succeeded in that turn, and those replies are not checked.

| Phase | Row and turn | Replies | Call | No call | Check fired |
| --- | --- | --- | --- | --- | --- |
| baseline | D 1 | 5 | 1 | 4 | 4 |
| baseline | D 2 | 5 | 0 | 5 | 5 |
| baseline | V 1 | 5 | 0 | 5 | 5 |
| baseline | V 2 | 5 | 0 | 5 | 0 |
| baseline | A | 5 | 4 | 1 | 1 |
| with the change | D 1 | 5 | 4 | 1 | 0 |
| with the change | D 2 | 5 | 0 | 5 | 0 |
| with the change | V 1 | 5 | 0 | 5 | 0 |
| with the change | V 2 | 5 | 0 | 5 | 0 |
| with the change | A | 5 | 5 | 0 | 0 |

Against the rule:

1. The baseline check fired on 14 of the 20 replies of rows D and V, so the defect reproduced.
   Row D's replies were the message alone, such as "I've scheduled the design review for Friday
   at 10:00 AM." and, made formal, "Please be advised that the design review has been scheduled
   for Friday at 10:00 AM." Every first turn of row V wrote an email holding "I've scheduled our
   one-to-one for Tuesday at 15:00."; the shortened emails of V 2 matched no form.
2. With the change it fired on none of the 16 replies of rows D and V that made no call, 11 of
   which hold a "scheduled" form.
3. Row A made a call that succeeded in all five chains with the change, so no reply there could
   be checked. The baseline's one reply with no call ran only `list_scheduled` and said "OK. I've
   set a reminder for your call with Ana at 14:00 on Friday", and the changed function fires on
   it beside row A's message.
4. The changed function fires on all nine corpus claims, and on the seven quoted ones with the
   reminder turn or with "What is 17 times 23?" as the chain's second message.
5. No stored message of rows D and V holds the note with the change, against 14 in the baseline.

The change passes and ships. A first turn of row D called `schedule_task` and stored a reminder
"Design review" in 1 of 5 baseline chains and 4 of 5 with the change, though nobody asked for one
([R-872](../refinements/tasks/872-a-request-to-draft-a-message-can-schedule-a-reminder.md)).
Runs: `runs/{base,after}.jsonl` in the same folder. Whether memory caused the call is measured
below.

## The unrequested reminder: rows and the rule, written before the first run

Row D's first turn runs in a fresh session, so before it the cortex reads only the system prompt,
the tool list and the memories recall returns: the change measured above alters the note on a
reply and nothing the first turn reads, except through what memory recorded. Memory recorded each
exchange as `User`, an optional `Tools run` line and `Assistant`, so at the end of the runs above
the `cortexn5` memory table held 131 rows, 25 of them about the design review: 11 ending with
`UNSCHEDULED_CLAIM_NOTE`, 6 naming `schedule_task (succeeded)` on their `Tools run` line, and 8
with neither. The baseline's one call came after 10 noted rows; the five chains with the change
then added a run row each time one called.

**2026-10-15**, the same stack and driver, row D only, five chains per condition, drawn chain by
chain in the order K, N, R, E so a drift in time reaches every condition alike. Before each chain
the memory table is reset to its condition from a copy taken before the first run:

| Condition | Memory before each chain | Brain |
| --- | --- | --- |
| K | all 131 rows | with the change |
| N | K without the 6 run rows | with the change |
| R | K without the 11 noted rows | with the change |
| E | emptied | with the change |
| O | emptied, drawn only if rule 3 calls for it | built from the commit before the change |

`c(X)` is the number of chains of condition X with a `schedule_task` call in either turn,
counted whether or not it succeeded.

**Rule.**

1. Memory is a cause when `c(K)` is 3 or more and `c(E)` is 1 or less.
2. Then the run rows are the source when `c(R)` is 3 or more and `c(N)` is 1 or less, the noted
   rows when the reverse holds, both when both are 3 or more, and neither alone otherwise.
3. When `c(E)` is 3 or more, memory is not required and O is drawn. If `c(O)` is also 3 or more,
   the change is not the cause and the call comes from the request alone. If `c(O)` is 1 or less,
   the result contradicts the reading above, since the change cannot reach a fresh chain's first
   turn except through memory; it is written here and nothing ships.
4. Any other count decides nothing, and a `c(K)` of 1 or less means the earlier 4 of 5 is not
   reproduced with memory held fixed: both are nulls, nothing ships and the task stays open
   with the counts.

**A candidate fix** is drawn on the condition that reproduced the call, five chains, plus five
chains of row A. It passes when that condition's count is 1 or less, every first turn of row D
still writes the message, and row A still calls `schedule_task` in 4 or more of 5 chains. A
failure is a null and the candidate does not ship.

## The unrequested reminder: results

**2026-10-15**, all twenty chains completed, drawn by `draw.py mem KNRE 5`. Each memory reset
was checked by the row count it left: 131, 125, 120 and 0.

| Condition | Chains | `c(X)` | Calls that succeeded | First turns listing options |
| --- | --- | --- | --- | --- |
| K | 5 | 1 | 1 | 0 |
| N | 5 | 0 | 0 | 0 |
| R | 5 | 1 | 1 | 0 |
| E | 5 | 0 | 0 | 2 |

Every call was in a first turn. Rule 4 applies: `c(K)` is 1, so the earlier 4 of 5 is not
reproduced with memory held fixed, O is not drawn, and nothing ships. Memory did change the
reply: every first turn with memory wrote the one line the recalled exchanges held, "Hi team,
I've scheduled the design review for Friday at 10:00 AM.", while two of the five with memory
emptied offered several options instead.

## A replay of the earlier sequence: written before its run

The earlier run with the change differed from condition K in two ways: it drew rows D, V and A in
turn, and its memory grew as each exchange was recorded, from 103 rows (12 about the design
review, 11 of them noted and one a run row) to the 131 above. Condition S repeats that: the same
three rows in turn, five chains, on the brain with the change, memory reset once to the 103 rows
recorded before that run and then left to grow.

1. If `c(S)` is 3 or more, the call depends on what the run itself records; the task is
   corrected to say so and the next row removes each chain's own records. Nothing ships.
2. If `c(S)` is 1 or less, the earlier 4 of 5 does not reproduce in its own sequence; the task is
   corrected to state the rate measured over every chain with the change, and its next row is a
   larger draw that can price that rate. Nothing ships.
3. A `c(S)` of 2 decides nothing.

**Result, 2026-10-15**, `draw.py seq S 5 DVA`: `c(S)` is 1 (chain 2, which succeeded; chain 4
ran only `list_scheduled`), and every row A chain called `schedule_task`. Rule 2 applies. Over
every chain this page drew on the brain with the change, a first turn of row D called
`schedule_task` in 7 of 30: 4 of 5 in the earlier run, 3 of 25 here, none of them with memory
emptied.

## The rate: written before its run

Condition L draws the first turn of row D alone, 40 chains each of K and E, alternately, with
memory reset before each chain, on the brain with the change.

1. Each condition's rate is its count over 40 and is written into the task.
2. If `c(E)` is 4 or more, the request alone calls `schedule_task` at a rate a 40-chain row can
   measure, and the task's next step is a tool description sentence drawn on 40 chains of E and
   five of row A, passing when its count is at most a third of `c(E)` and row A calls in 4 or more
   of 5.
3. If `c(E)` is 1 or less and `c(K)` is 6 or more, memory is required, and the task's next step
   splits K into N and R at 40 chains each.
4. Otherwise the rate is below what these rows can split, and the task waits for an unrequested
   reminder reported from a real chat.

**Result, 2026-10-15**, `draw.py rate KE 40 F`, all 80 chains completed: `c(K)` is 1 of 40 and
`c(E)` is 0 of 40. Rule 4 applies, and nothing ships. Over the 105 chains drawn after the earlier
run, a first turn of row D called `schedule_task` in 4 of the 60 with memory and none of the 45
with it emptied. Memory set the reply's form again: 17 of the 40 first turns with memory emptied
offered several options, and none of the 40 with it. Method: `draw.py` and `tabmem.py` in the
same folder, `runs/{mem,seq,rate}.jsonl`; the copy of the memory table that each reset read was
dropped afterwards and the table was restored to its 131 rows.
