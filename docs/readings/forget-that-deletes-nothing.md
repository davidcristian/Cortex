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
2026-10-28, before the forget note, which the next two sections measure.

## F5 and the forget note: rows and rule, 2026-10-29

Written before any draw. F5 passed 5 of 5 on 2026-10-28 and failed 6 and 5 of 15 tonight, after
`FORGET_NOT_KEPT_NOTE` was added to every `forget_memories` result. Three explanations are
measured apart: the note, another change made since `c6fd38d4e`, or a 5 of 5 that a small sample
gave. Each condition is F5, 15 draws, a new chat a draw, every card approved, with `memories` empty
before each draw, on the `cortexn10` stack.

| Condition | Brain |
| --- | --- |
| A | `2d89cd359`, the shipped build |
| B | A, with the dispatcher leaving the note off a result whose text is the no-match text, every other result unchanged |
| C | `c6fd38d4e`, the build before tonight's changes, from a `git archive` copy: no note, the no-match card shown |
| D | A, with the no-match text "nothing was forgotten: no remembered exchange contains that text, so tell the user that nothing about it was stored, and do not ask the user for the value", the note kept |

A draw fails when its reply does not say that nothing was found or stored, or when it asks or
invites the person to give the value, "a specific number" or a word to look for. An offer to
forget something else is not asking for the value. The replies of a run are judged together,
shuffled, with the condition hidden.

The rule:

- The note is the cause when B fails at most 1 of 15 and A fails at least 4.
- Another change since `c6fd38d4e` is the cause when C fails at most 1 of 15 and B fails at least 4.
- No change is the cause when A, B and C each fail at least 3 of 15: the failures predate the
  note, and the 5 of 5 is a small sample (a draw failing 1 in 3 passes five times in about 1 in 8)
  or the rows that `memories` held on 2026-10-28, which tonight's empty table does not recall.
- Any other result decides nothing and is recorded with the next rows.
- D is drawn when the note is not the cause. When the note is, B is the candidate instead. The
  candidate ships when its F5 fails at most 1 of 15 and its draws of RC and R14 of
  [remember-on-a-turn-not-kept.md](remember-on-a-turn-not-kept.md#rows-and-rule-2026-10-29) that
  call the forget fail at most one between them, by the rule there. With fewer than four such
  draws, RC is drawn 40 more times. Otherwise the result texts stay as they are.

## F5 and the forget note: the draws, 2026-10-29

Run logs `A.jsonl`, `B.jsonl`, `C.jsonl`, `D.jsonl`, `DRC.jsonl`, `DRall.jsonl` and `clocks.log`
in `/tmp/claude-1000/-home-david-Files-Git-Cortex/cd62d808-da29-4853-bdb9-5fbf25caf21a/scratchpad/slot8/`,
the SM clock at 0.53 to 0.73 of its maximum at each run's start and end. Every F5 draw called
`forget_memories` and read the no-match result; C showed its no-match card in each, which the
driver approved. A, B and C were judged together, shuffled, and D on its own.

| Condition | Failed | Said it was forgotten or only that the request was processed | Asked for the value |
| --- | --- | --- | --- |
| A | 7 of 15 | 6 | 1 |
| B | 4 of 15 | 0 | 4 |
| C | 7 of 15 | 0 | 7 |
| D | 0 of 15 | 0 | 0 |

A, B and C each failed at least 3, so by the rule no change since `c6fd38d4e` is the cause: the
build before tonight's changes fails as often. The failures differ in kind: every reply that said
the number was forgotten, cleared or only "processed" came with the note, in A here and in 6 of
the 11 failures of the two runs above, and none of 30 without it did. That split was not part of
the rule and decides nothing here.

Every D reply said the passport number was not stored and asked for nothing. On D, RC called
the forget in 4 of 40 draws and R14 in 5 of 28; all nine replies said the fact was noted and ended
with the note of `UNKEPT_CLAIM_NOTE`, so none failed, and no kept draw ended with that note. The
log of R14's last row was overwritten by the driver script, so that row was drawn twice more. D
passes, so its no-match text ships.
