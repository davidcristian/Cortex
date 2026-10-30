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
