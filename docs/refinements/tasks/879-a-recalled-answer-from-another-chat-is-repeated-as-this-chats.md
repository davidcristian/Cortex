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
4 of 5 draws on HEAD, and in 2 and 3 of 5 with either replay text tried for
[R-878](878-a-handoff-whose-deep-reply-was-not-stored-reads-as-answered.md)
([readings](../../readings/handoff-reply-not-kept.md), row L). The fifth HEAD draw paraphrased a
recalled deep reply.

## Reproduction

Row L of the readings: on the shared stack, with memory holding another chat's exchange for the
same follow-up question and stored deep replies to the odd-numbers handoff question, seed a chat
holding that question and the hand-over sentence and no deep reply, then send the follow-up over
`Converse`.

## What to do

Change how a recalled exchange is framed, not the replay. For example the recalled block could
say that an answer in a memory belongs to that other chat and says nothing about this one. Draw
row L against the readings' 4 of 5 rule before it ships, with rows C and L2 beside it.

## History

- 2026-10-16: filed from R-878's draws, where no replay text moved this row.
