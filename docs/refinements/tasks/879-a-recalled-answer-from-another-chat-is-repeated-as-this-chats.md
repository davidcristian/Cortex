# A recalled answer from another chat is repeated as this chat's

**Status:** declined 2026-10-17
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

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

Keep the other chat's exchange out of the pool. Two framings of the recalled block and a rank
prompt holding this chat's last exchange each left row L at 1 of 5 or fewer, and with the exchange
shown the judge kept the same four memories: the answer is on this chat's subject, and no note
says which chat it came from. In a chat with an earlier turn, leave out of recall an exchange
whose question is this turn's question word for word. Add the readings' row Q, which checks that
cost, before drawing, then draw the six rows under the readings' rule
([next idea](../../readings/handoff-reply-not-kept.md#recall-rank-with-the-last-exchange)).

## History

- 2026-10-16: filed from the draws for the replay of an unanswered handoff, where no replay text
  moved this row.
- 2026-10-16: two framings of the recalled block drawn and backed out: each memory marked with its
  record time and as from another conversation, under a note that its answer was given there,
  and then the same with its labels as "Asked there" and "Answered there". L stayed at 0 of 5 for
  each against 1 on HEAD; wanted recall (rows R and F) kept 5 of 5
  ([readings](../../readings/handoff-reply-not-kept.md#recall-framing-rows-and-rule)).
- 2026-10-17: the judge's rank prompt given this chat's last exchange and a note that every memory
  came from an earlier conversation, drawn and backed out: L passed in 1 of 5 against 0 on HEAD,
  L2 fell from 4 to 3, and R and F kept 5 of 5. A dump showed the judge kept the same four
  memories as on HEAD ([readings](../../readings/handoff-reply-not-kept.md#recall-rank-with-the-last-exchange)).
- 2026-10-17: declined. In a chat with an earlier turn, recall left out of the pool an exchange
  whose question matched this turn's word for word: L passed in 5 of 5 against 1 on HEAD, and the
  readings' row Q, a repeated question whose answer only that exchange holds, fell from 5 to 0. No
  memory says whether a question refers to its own chat, so any narrower drop moves the same cost,
  and the defect only repeats the deep model's own answer to the same question
  ([readings](../../readings/handoff-reply-not-kept.md#recall-without-a-repeated-question)).
