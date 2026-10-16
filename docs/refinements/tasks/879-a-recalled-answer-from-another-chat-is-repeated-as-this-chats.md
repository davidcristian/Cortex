# A recalled answer from another chat is repeated as this chat's

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-16

A turn's exchange is recorded as `User: <question> / Assistant: <reply>` (`record_exchange`,
`cortex_core/turn_output.py`), and recall gives it to a later chat under "Relevant memories from
earlier conversations" (`cortex_core/turn_context.py`). Memory held the flow's own follow-up turn,
"What did the deep model say, in one line?" asked in another chat, whose one-line answer
paraphrased a deep reply stored by a third chat. In a chat whose own deep reply was not stored,
the same question was answered by repeating that recalled answer word for word as this chat's, in
4 of 5 draws before the replay of an unanswered handoff, where the fifth paraphrased a recalled
deep reply. With the shipped replay text it was still repeated in 2 of 5, and in 3 of 5 with a
text that also named memory ([readings](../../readings/handoff-reply-not-kept.md), row L).

## Reproduction

Row L of the readings: on the shared stack, with memory holding another chat's exchange for the
same follow-up question and stored deep replies to the odd-numbers handoff question, seed a chat
holding that question and the hand-over sentence and no deep reply, then send the follow-up over
`Converse`.

## What to do

Change what is recalled, not how it is shown: two framings of the recalled block left row L at 0
of 5. The judge ranks the pool on the question alone, and this question names nothing in the chat,
so the other chat's exchange asking the same words is the nearest by cosine and the judge keeps
it. Give the rank prompt this chat's last exchange, then draw the readings' five rows under their
rule, where R and F check that wanted recall does not fall.

## History

- 2026-10-16: filed from the draws for the replay of an unanswered handoff, where no replay text
  moved this row.
- 2026-10-16: two framings of the recalled block drawn and backed out: each memory marked with its
  record time and as from another conversation, under a note that its answer was given there,
  and then the same with its labels as "Asked there" and "Answered there". L stayed at 0 of 5 for
  each against 1 on HEAD; wanted recall (rows R and F) kept 5 of 5
  ([readings](../../readings/handoff-reply-not-kept.md#recall-framing-rows-and-rule)).
