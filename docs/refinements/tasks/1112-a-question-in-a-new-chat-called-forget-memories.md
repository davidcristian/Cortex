# A question in a new chat called forget_memories

**Status:** done 2026-11-11
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

In c1 draw 4 of [the readings](../../readings/correction-keeps-old-value.md), after a correction turn had deleted the only bike lock row, `What is my bike lock
code?` in a new chat called `forget_memories` (its text is redacted in the audit log). The call
matched nothing, so the reply `I don't have your bike lock code in my memory.` ended with
`UNMATCHED_FORGET_NOTE`, which tells the person about a forget they never asked for. One of 18
question turns; no card showed, so nothing was deleted.

## What to do

On 2026-11-11 the question did not call `forget_memories` again in 18 draws (no row, one row,
flow c1), but `Can you note that Anna likes plants?`, a message with no forget word either, called
it in 6 of 12 draws, and each call matched nothing and lost the fact
([readings](../../readings/correction-keeps-old-value.md#the-question-in-a-new-chat-2026-11-11)).
The cause is shared, so build for it rather than drawing the question again.

1. Build a typed refusal of `forget_memories` by name on a turn whose message holds no word that
   can retract something, in English, French, German, Spanish or Romanian: the word part of
   `_CAN_RETRACT` in `unasked_tools.py`, without its question mark, sentence and clause parts.
   Its safe direction keeps the tool: it also keeps it when the message holds a letter outside
   English, and when the chat's last reply names forgetting at all, not only in a question.
2. Write near misses as tests first, each keeping the tool: `And my address too.` after a reply
   that says it forgot, `Yes` after `Should I forget it?`, `Oublie mon adresse.`, `Vergiss das.`,
   `Get rid of my old number.`, `My code is 4862, not 4826.`, `That one is wrong.`
3. Replay every readings string and proxy user message through it; the rule is that no recorded
   message asking to forget is refused, with the count of refused messages beside it.
4. Pass rule for the draws, written before them: on the rebuilt brain every `forget_memories`
   call on `Can you note that Anna likes plants?` and `What is my bike lock code?` is refused by
   name, and the first keeps its row. The count of such calls is a separate figure, so the fix
   can ship when its form is rare.

## History

- 2026-11-10: filed from c1 draw 4 in [the readings](../../readings/correction-keeps-old-value.md).
- 2026-11-11: drawn 18 times without a repeat; the same call on the question asking to note
  a fact in 6 of 12 shows the cause is shared, so What to do is rewritten as a build with its
  rule. Left open, verified, for lack of slot time.
- 2026-11-11: done. `forget_unrequested` refuses the call by name as `FORGET_UNREQUESTED` on a
  message with no word that can retract something, no negation in the five languages and no
  letter outside English, unless the last reply names forgetting; the turn is recorded and gets no
  note about deleting ([readings](../../readings/forget-unrequested.md)).
