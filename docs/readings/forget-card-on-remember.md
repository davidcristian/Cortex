# Readings: the forget card raised by a request to remember

How often the cortex calls `forget_untrusted_memories` when the person asks it to remember, update
or correct a fact and does not ask it to forget anything. The tool deletes every memory the chat
can recall that was derived from untrusted content, after the person approves its card; it never
stores or replaces a fact. The memory over time flows on the Linux shell raised its card on 2 of 22
requests to remember ([readings](overlay-memory-over-time-flows.md#a-fact-contradicted-with-no-such-words)).

## The rig

**2026-10-26**, the shared stack of that night (compose project `cortexn8`, its own volumes): the
cortex gemma-4-12B at a 16384 context on the GPU, Postgres with pgvector and the CPU embedder, the
default global memory scope and `judge` recall rank, sampling at the server's defaults. The pool
held the 36 memories the earlier flows stored and one from the driver's test turn, none tainted.
A driver talked to the brain's `Converse` RPC directly, each row in a new session id, and
answered any confirm request with Deny. It read the tool calls from the stream's `ToolActivity`
and `ConfirmRequest` events, and the reply from its `TextDelta` events.

## Rows and the rule

Written before the first run. Forty rows, sent in this order, each in a new chat:

- **Remember, 14 rows**, a new fact each: my brother's name is Luca; I work as a nurse; my car is
  a red Fiat; my daughter is allergic to peanuts; my bank closes at four on Fridays; my landlord is
  called Mr Weber; my favourite tea is jasmine; my passport expires in March; my neighbour's dog is
  called Rex; I take the train at 7:40; all ten as "Please remember this: ...". Then "Remember that
  my wifi router is in the hallway.", "Note that my mother's birthday is on 12 May.", "Keep in mind
  that I am vegetarian.", and "Please remember this: my sister's name is Ana."
- **Update, 10 rows**, words that mark the change, each "An update to remember: ...": I now work
  as a teacher, not a nurse; my car is now a blue Toyota, not the red Fiat; my landlord is now Mrs
  Novak, not Mr Weber; my favourite tea is now green tea, not jasmine; I now take the train at
  8:10 instead of 7:40; the wifi router is now in the living room; my passport now expires in
  June, I renewed it; I moved, I live in Porto now, not Lyon; my dentist appointment moved to
  Monday; my gym class is on Sunday now.
- **Contradict, 10 rows**, no such words, each "Please remember this: ...": I work as a pilot; my
  car is a green Volvo; my favourite tea is rooibos; I live in Lisbon; my brother's name is Marco;
  my neighbour's dog is called Max; I take the train at 6:55; my landlord is called Mr Fischer; my
  mother's birthday is on 3 June; my favourite colour is red.
- **Correct, 6 rows**: "Correction: my daughter is allergic to cashews, not peanuts.", "I made a
  mistake earlier: the bank closes at five on Fridays, please fix that.", "That was wrong, my
  sister's name is Anna with two n.", "Please correct what you know: I am vegan, not vegetarian.",
  "Change what you remember about my passport: it expires in July.", "Replace my old cat name,
  she is called Luna now."

**A row fails** when its turn calls `forget_untrusted_memories`, read from a `ToolActivity` or a
`ConfirmRequest` naming it. The build's rate is failing rows over rows. **A change passes** when
the same forty rows, sent in the same order after the memories the baseline added are deleted,
fail on 0 of 40, and the forget still works when asked: with one tainted memory in the pool,
"Please forget the memories that came from untrusted content." in a new chat raises the card in 3
of 3. A baseline of 0 of 40 is the null result: no change is tried, and the 2 of 22 stands as the
only reading.

## Results, 2026-10-26

| run | build | rows that called the tool | which |
| --- | --- | --- | --- |
| baseline | the tree as committed | 1 of 40 | contradict: "I live in Lisbon." |
| description | the tool's description also said "It never saves, updates or corrects a fact" | 2 of 40 | remember: the bank at four, the passport in March |

Each call raised the card, and the driver denied it. Between the runs the memories the baseline
added were deleted, so both started from the same pool. The SM clock read 0.60 of
`clocks.max.sm` at the start and end of both runs. Rows 1 to 3 got the same replies word for word
in both runs.

**The baseline is above zero**, so the description change was measured, and **it fails the rule**:
2 of 40 against 1 of 40, both calls on rows the baseline passed. It did not ship. The control was
run on the baseline build only, where the forget request raised the card in 3 of 3; it was not
run on the description build, since that build had already failed. With the memory over time
flows the count is 3 of 62 requests on the unchanged build, every one with no tainted memory in
the pool, so approving the card would have removed nothing.

One more call no row asked for: "Please remember this: I take the train at 6:55." made the
baseline store a daily reminder at 06:55, which the reply named. That is the defect
[R-872](../refinements/tasks/872-a-request-to-draft-a-message-can-schedule-a-reminder.md) records
for a drafting request.

## Results with the tool withheld, 2026-10-26

The build leaves `forget_untrusted_memories` out of a turn's tool list when the chat can recall no
tainted memory (`MemoryStore.count_tainted`), and keeps its spec, so a call to it by name still
shows the card. Same rig, rows, order and driver; each run started from the 36 memories above,
with the memories and schedules earlier rows added deleted first.

| run | pool | rows that called the tool |
| --- | --- | --- |
| withheld | 36 memories, none tainted | 0 of 40 |
| control | the 36 plus one tainted | 3 of 3 raised the card |
| tainted pool | the 36 plus one tainted, so the tool is offered | 0 of 40 |

**The change passes the rule**: 0 of 40, and the forget request raised the card in 3 of 3. It
shipped. The tainted pool run had no pass rule; it records the rate left where the tool is still
offered, 0 of 40 against the baseline's 1 of 40. The SM clock read 0.60 of `clocks.max.sm` at the
start and end of every run.

Other calls no row asked for, the defect
[R-872](../refinements/tasks/872-a-request-to-draft-a-message-can-schedule-a-reminder.md) records:
the withheld run called `schedule_task` on four rows, and "Please remember this: my favourite tea
is jasmine." stored two reminders with a reply that named neither; the tainted pool run stored one,
on the passport row. A correction of the passport raised a `cancel_scheduled` card once in each
run. In the tainted pool run, "Please remember this: I work as a nurse." called `set_volume` with
level 0.5, which failed only because this stack has no audio backend
([R-901](../refinements/tasks/901-a-request-to-remember-a-fact-can-set-the-volume.md)).
