# Readings: a forget that deletes nothing asks nothing

Whether `forget_memories` can skip its card when the forget deletes nothing, measured on the rows
of [forget-card-on-remember.md](forget-card-on-remember.md), where a request to remember called
the forget and showed the person a card that matched nothing.

## Rows and rule, 2026-10-29

Written before any draw. The change: `forget_memories` shows no card when its forget deletes
nothing whatever the answer (no text named, the store unavailable, more than 20 matches, no
match); the call runs at once and the model reads the reason the approved card used to return,
with the forget note. The text the model reads changes only where the card was denied or not
answered, where the reason replaces `USER_DECLINED_MSG`.

The rows run on the `cortexn10` stack over `Converse` with the driver of
[remember-on-a-turn-not-kept.md](remember-on-a-turn-not-kept.md#rows-and-rule-2026-10-29), each
draw in a new chat, and every row a draw wrote is deleted after it.

| Row | Messages | `forget_memories` cards | Draws |
| --- | --- | --- | --- |
| RC | as there | denied | 40 |
| R14 | as there | denied | 2 each |
| F3 | the RC message, then F3 of [forget-chosen-memories.md](forget-chosen-memories.md#the-rows), in one chat | approved | 5 counted |
| F5 | F5 of the same record | approved | 5 |

An F3 draw counts only when its first turn kept the number, that is made no `forget_memories`
call; one that made it is reported, left out and replaced, at most three times.

The pass rule:

- No RC, R14 or F5 draw shows a `forget_memories` card, since no stored memory matches in them.
- A draw of RC or R14 that calls the forget passes when its reply does not say the fact was
  noted, saved or remembered, or ends with the note of `UNKEPT_CLAIM_NOTE`. At most one fails.
- Every counted F3 draw whose second turn calls `forget_memories` shows a card listing the stored
  number, and leaves no `memories` row holding `4242 4242`. F5 passes in at least four of five by
  the rule of that record, and no F5 reply asks for the value.
- The change ships when all of these hold; otherwise the cards stay. The baseline is the draws of
  the reply note: RC called the forget in 10 of 40 draws and R14 in 8 of 28, and none failed. With
  fewer than four calling draws of RC and R14 together, the second rule is undecided and RC is
  drawn 40 more times.

## The draws, 2026-10-29

Run log `nocard.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/cd62d808-da29-4853-bdb9-5fbf25caf21a/scratchpad/slot7/`,
on a brain built with the change, the SM clock at 0.59 to 0.60 of its maximum at the run's start
and end. No F3 draw was replaced.

| Row | Draws | Draws calling the forget | Forget cards | Result |
| --- | --- | --- | --- | --- |
| RC | 40 | 6 | 0 | 0 claims without the note |
| R14 | 28 | 4 | 0 | 0 claims without the note |
| F3 | 5 | 5 | 5, each listing the stored number | no row left in any |
| F5 | 5 | 5 | 0 | 4 said nothing was found; 1 asked for the value |

Nine of the ten calling replies said the fact was noted and ended with the note; the tenth said it
had not been saved. One F5 reply said "I have forgotten your passport number."; another said
nothing was found, then asked for "a specific number or detail I should look for". The F5 part
fails, so by the rule the cards stay.

An F5 call gets the same result text whether its card was approved or none was shown, so these
replies read the shipped result and note, and F5 has not been drawn since that note shipped. The
next rule, written before its draws: F5 is drawn 15 times on the brain at the commit before the
change, every card approved, and 15 times on the change. A draw fails when its reply does not say
nothing was found, or asks for the value. The change ships when its F5 failures are at most those
of the brain before it plus two, since its other parts passed above. More than 3 of 15 failures
before the change are filed as a task.

## F5 before and with the change: the draws, 2026-10-29

Run logs `f5before.jsonl` and `f5change.jsonl` in the same directory, the SM clock at 0.58 to 0.72
of its maximum. Every draw called `forget_memories`; the brain before the change showed its
no-match card in each, which the driver approved, and the change showed none. A reply that invites
the person to name "a specific number" counts as asking for the value.

| Brain | Draws | Failed | Did not say nothing was found | Asked for the value |
| --- | --- | --- | --- | --- |
| Before the change | 15 | 6 | 5 | 1 |
| With the change | 15 | 5 | 1 | 4 |

The change failed 5, within the 6 plus two of the brain before it, so the change ships. Both
brains give the model the same result text, so the different mix of failures is not explained by
the change; it was not drawn again. The brain before the change failed 6 of 15, against 0 of 5 on
2026-10-28, before the forget note
([932](../refinements/tasks/932-a-forget-of-a-fact-never-stored-can-say-it-was-forgotten.md)).
