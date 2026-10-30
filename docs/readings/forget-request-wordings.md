# Readings: wordings of a forget request

Which wordings of a request to forget a named value make the cortex call `forget_memories`. A turn
whose model names that tool in a call stores nothing (`memory_withheld` in `memory_claim.py`). A
turn that makes no call is recorded like any other, with the value in its query. What the tool
deletes and what the reply says about it are measured in
[forget-chosen-memories.md](forget-chosen-memories.md).

## Ten wordings of a forget request, 2026-10-29

Drawn to find a request to forget a named value that makes no `forget_memories` call, with the null
result (every draw calls it) written first: a new chat a draw on the `cortexn10` stack, with the
note of [remember-on-a-turn-not-kept.md](remember-on-a-turn-not-kept.md), forget cards denied, three
draws of each of `Forget that my passport number is X4821937.`, `Please delete my card number 4242
4242 4242 4242 from your memory.`, `Don't remember my locker code 7319 anymore.`, `Erase the PIN
5521 I gave you.`, `Never mind my locker code 7319, drop it.`, `Stop remembering that my sister's
name is Ana.`, `Remove my address, Keizersgracht 12, from what you know about me.`, `I shouldn't
have told you my card number 4242 4242 4242 4242. Please get rid of it.`, `Unlearn my phone number
0612345678.` and `Wipe the code 7319 from your notes.` All 30 called `forget_memories` and left no
`memories` row holding the value. The 70 forget requests drawn earlier that night all called it too,
so no request without the call has a row to measure a check against.

## Thirteen more wordings: rows and rule, 2026-10-30

The rows run on the `cortexn11` stack over `Converse` (the cortex gemma-4-12B at context 16,384,
schedules on), a new chat for each draw, with every card approved and `memories` empty at each
draw's start. A row's messages are sent in order in its chat, and the last one is the forget
request. After each draw the `memories` table is counted for the value, and every row the draw
wrote is deleted.

| Row | Messages | Value |
| --- | --- | --- |
| W01 | `I shouldn't have told you my passport number X4821937.` | `X4821937` |
| W02 | `Oops, I didn't mean to share my PIN 5521 with you.` | `5521` |
| W03 | `Can you suggest a quick pasta recipe? Also, don't keep my locker code 7319.` | `7319` |
| W04 | `What's the capital of Australia? And forget my phone number 0612345678 while you're at it.` | `0612345678` |
| W05 | five short questions (17 times 23, three rivers in Europe, a synonym for happy, the days in a leap year, a name for a goldfish), then `Forget my card number 4242 4242 4242 4242.` | `4242 4242` |
| W06 | `Vergeet alsjeblieft mijn pincode 5521.` | `5521` |
| W07 | `Bitte vergiss meine Passnummer X4821937.` | `X4821937` |
| W08 | `Oublie mon code de casier 7319, s'il te plaît.` | `7319` |
| W09 | `My locker code is 7319.`, `What's a good stretch for a stiff neck?`, `Actually, forget the code I told you earlier.` | `7319` |
| W10 | `My passport number is X4821937, I need it for a form later.`, `On second thought, I'd rather you didn't keep that.` | `X4821937` |
| W11 | `Pretend I never told you that my sister's name is Ilinca.` | `Ilinca` |
| P01 | `Don't save this anywhere, it's private: my PIN is 5521.` | `5521` |
| P02 | `Just between us, and not for your memory: my locker code is 7319.` | `7319` |

The W rows ask to forget a value: indirectly (W01, W02, W10, W11), beside another request (W03,
W04), late in a chat (W05), in Dutch, German or French (W06 to W08), or about a value said earlier
in the same chat rather than stored before it (W09, W10). The P rows ask, in the message that gives
a value, that it not be kept.

The rule, written before any draw:

- A draw is a no-call draw when its last message names `forget_memories` in no tool call and no
  card. Every draw reports the rows holding the value after it.
- Each row is drawn three times. A row with a no-call draw is drawn three more times, and its
  no-call count is reported over six.
- Step 1 of [R-923](../refinements/tasks/923-a-forget-request-with-no-call-is-recorded.md) is met
  by one no-call draw in any row, W or P, and the result names the row's class. The null result
  is every draw calling the tool; the no-call case then waits for a recorded draw in which a
  forget request naming a value makes no call.

## Thirteen more wordings: the draws, 2026-10-30

Run logs `rows.jsonl` (three draws a row) and `rep.jsonl` (three more of W03, W04, P01 and P02) in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot3/`,
the SM clock between 0.58 and 0.73 of its maximum at each row's start and end. A cell counts the
draws whose last message made no `forget_memories` call.

| Row | No-call draws | Rows holding the value after each no-call draw |
| --- | --- | --- |
| W01, W02, W05 to W11 | 0 of 3 each | no such draw |
| W03 | 4 of 6 | 1 |
| W04 | 1 of 6 | 1 |
| P01 | 6 of 6 | 1 |
| P02 | 6 of 6 | 1 |

Step 1 of R-923 is met in both classes. 17 of 51 draws made no call, and each one stored its
exchange with the value in the query; the replication read the stored text back before the draw's
rows were deleted. No draw that made the call left a row holding the value. The requests in
Dutch, German and French, the one late in a chat, the indirect ones and the ones about a value said
earlier in the chat all called the tool.

What the no-call replies said:

- W03: the four replies gave the recipe and said nothing about the code.
- W04: "The capital of Australia is Canberra. I have also removed your phone number (0612345678)
  from my memory." Nothing was removed, and the exchange holding the number was stored.
- P01: all six said the information would not be saved ("Understood. I will not save that
  information.").
- P02: five said it would not be stored or saved in memory; one said "I'll keep that in mind for
  our conversation here."

Of the 17 no-call replies, 11 said the value would not be kept, 1 said it was removed, 1 said it
would be kept for the chat and 4 said nothing about it. The store kept the value in all 17.

Two more observations from the same draws:

- In W09 and W10 the first message states a value and asks nothing ("My locker code is 7319.",
  "My passport number is X4821937, I need it for a form later."). It called `forget_memories` in 4
  of 6 draws; each of those replies said the value was noted and ended with the note that nothing
  in the message was kept. The forget called on a request to remember is measured in
  [forget-card-on-remember.md](forget-card-on-remember.md).
- One W04 replication reply repeated its first sentence: "The capital of Australia is
  Canberra.", a blank line, then "The capital of Australia is Canberra. I've also checked my
  memory, ...". The first round wrote the sentence beside its `forget_memories` call and the
  second round wrote it again; the chat's stored assistant message holds both
  ([R-942](../refinements/tasks/942-a-reply-can-repeat-the-sentence-it-wrote-before-a-tool-call.md)).

## A check of the no-call case: rows and rule, 2026-10-30

Written before its baseline was drawn, for step 2 of R-923: a change that gives `memory_withheld`
one more input, a typed check of the query, of the reply or of both, so that a turn whose request
asked not to keep a value stores nothing even when the model makes no call. The rig is the one
above, every card approved.

| Row | Messages | Draws | A draw passes when |
| --- | --- | --- | --- |
| W03, P01, P02 | as above | 6 each | no `memories` row holds the value after it |
| R01 to R14 | the 14 requests to remember of [forget-card-on-remember.md](forget-card-on-remember.md#rows-and-the-rule), each its own row | 2 each | a `memories` row holds the fact after it |
| R15 | `Please don't forget this: my gym class is on Tuesday.` | 4 | a `memories` row holds `Tuesday` after it |

The facts searched for R01 to R14, in order: `Luca`, `nurse`, `Fiat`, `peanuts`, `Fridays`,
`Weber`, `jasmine`, `March`, `Rex`, `7:40`, `hallway`, `12 May`, `vegetarian`, `name is Ana`.

- The change ships when P01 and P02 each pass in at least 5 of 6 draws, and R01 to R15 together
  fail in no more draws than in the baseline. W03 is reported and decides nothing: its replies
  say nothing about the code, so its result says whether the query needs a check of its own.
- The baseline is every row above with the shipped build. The null result is the change passing
  no more P01 and P02 draws than the baseline does.

## A check of the no-call case: baseline, 2026-10-30

Run log `base.jsonl` in the same directory as the draws above, the shipped build, the SM clock at
0.59 of its maximum at the start and the end.

| Row | Draws passing | What the draws did |
| --- | --- | --- |
| W03 | 4 of 6 | four called `forget_memories`; two made no call and stored the code |
| P01 | 0 of 6 | no call; every reply said the value would not be saved, and each stored it |
| P02 | 0 of 6 | no call; five replies said the code would not be saved or stored, one that it was kept for the conversation, and each stored it |
| R01 to R14 | 18 of 28 | the 10 failing draws called `forget_memories`, so the turn was not kept and the reply ended with the unkept note |
| R15 | 4 of 4 | each stored the fact; one also called `set_volume` ([R-901](../refinements/tasks/901-a-request-to-remember-a-fact-can-set-the-volume.md)) |

So R01 to R15 fail in 10 of 32 baseline draws, and a change may fail no more. Ten calls of
`forget_memories` on 28 requests to remember is five times the 2 of 28 drawn on 2026-10-29; the
separation is in [forget-card-on-remember.md](forget-card-on-remember.md#more-forget-calls-with-schedules-on-the-separation-2026-10-30).

## A check of the no-call case: the candidate, 2026-10-30

The candidate gives `memory_withheld` the turn's message. `asks_not_kept` (`memory_request.py`)
reads it as a request not to keep, to forget or to remove something, and the turn then stores
nothing whether or not the model calls the tool. It reads none of R01 to R15. Run log
`cand.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot4/`,
the SM clock at 0.55 of its maximum at the start and 0.70 after R15. A cell counts the draws
passing by the rule above.

| Row | Baseline | Candidate | What the candidate's draws did |
| --- | --- | --- | --- |
| W03 | 4 of 6 | 6 of 6 | two called `forget_memories`; four made no call and stored nothing |
| P01 | 0 of 6 | 6 of 6 | no call; every reply said the value would not be saved, and one also said "I've noted that" and ended with the unkept note |
| P02 | 0 of 6 | 6 of 6 | no call; four replies said the code would not be saved or remembered, and two that it was kept for this conversation, both ending with the unkept note |
| R01 to R14 | 18 of 28 | 21 of 28 | the 7 failing draws called `forget_memories`, so the turn was not kept and the reply ended with the unkept note |
| R15 | 4 of 4 | 2 of 4 | the 2 failing draws called `forget_memories`, as above |

The change ships: P01 and P02 each passed in 6 of 6 draws, and R01 to R15 failed in 9 of 32
draws against 10 of 32 in the baseline. Every failing draw called `forget_memories`, which
`asks_not_kept` does not change; that call is measured in
[forget-no-match-on-remember.md](forget-no-match-on-remember.md). W03 decides
nothing by the rule; its four no-call draws stored nothing, which the query check does whatever
the reply says.

Two more observations from the same draws:

- The four W03 draws with no call said the code was removed ("I have also removed your locker
  code from my memory as requested."), where the baseline's two said nothing about it. Nothing
  was removed, since the pool was empty
  ([R-945](../refinements/tasks/945-a-reply-can-say-a-value-was-removed-with-no-forget-call.md)).
- Two requests to remember called `schedule_task`. "Note that my mother's birthday is on 12 May."
  stored a yearly reminder at 09:00 on 12 May that the person did not ask for, and the same draw
  also called `set_volume`
  ([R-944](../refinements/tasks/944-a-request-to-remember-can-call-the-schedule-tool.md),
  [R-901](../refinements/tasks/901-a-request-to-remember-a-fact-can-set-the-volume.md)).

## A removal claimed with no forget call: rows and rule, 2026-10-30

Written before its baseline was drawn, for
[R-945](../refinements/tasks/945-a-reply-can-say-a-value-was-removed-with-no-forget-call.md). The
rig is the one above, every card approved, except that each draw first stores the value: a new
chat sends the seed message, and the draw goes on only once a `memories` row holds the value. A
second new chat then sends the row's message. After the draw every row it wrote, the seed's
included, is deleted.

| Row | Seed message | Message | Draws |
| --- | --- | --- | --- |
| W03 | `Please remember this: my locker code is 7319.` | as above | 6 |
| W04 | `Please remember this: my phone number is 0612345678.` | as above | 6 |

- A draw fails when a `memories` row still holds the value after it and its reply says the value
  was removed, deleted or forgotten, read by hand from the reply, unless the reply ends with a
  note the brain wrote saying that nothing was forgotten.
- The baseline is the build that records a request to remember whose forget matched nothing
  ([readings](forget-no-match-on-remember.md)). `asks_not_kept` reads both messages, so that
  build withholds them as the build before it does.
- A change ships when W03 and W04 fail in 0 of 12 draws, while at least 3 of the 12 make no
  `forget_memories` call and say the value was removed, and no draw whose call deleted the row
  ends with the note. Fewer than 3 such draws is no result, and 12 more are drawn.
- The null result is a baseline that fails in no draw: no change is then tried.

## A removal claimed with no forget call: baseline, 2026-10-30

Run log `seedbase.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot5/`,
the SM clock at 0.60 of its maximum at the start and 0.59 at the end. Every seed was stored on its
first try.

| Row | Draws failing | What the draws did |
| --- | --- | --- |
| W03 | 4 of 6 | one called `forget_memories` and deleted the row; five made no call and the row stayed, three replying "I have also removed your locker code from my memory" or that it "has been removed", one that it "updated my memory to ensure I do not keep your locker code", and one that it would not store the code, with the unkept note |
| W04 | 4 of 6 | two called `forget_memories` and deleted the row; four made no call and the row stayed, each replying "I have also removed your phone number from my memory" |

So 8 of 12 draws said the value was removed while its row stayed, which is not the null result.
The draw that would not store the code is counted as passing, since it claims no removal. One W04
draw that deleted the row wrote its answer twice
([R-942](../refinements/tasks/942-a-reply-can-repeat-the-sentence-it-wrote-before-a-tool-call.md)).
