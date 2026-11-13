# A statement after a courtesy question keeps the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`_asks_in_english` (`forget_unrequested.py`) counts an English statement of a fact only after a
last reply holding no `?`, so a statement can answer the assistant's own question in a forget flow
(`Which code is it?`). The model ends most replies with an unrelated question, such as `How can I
help you today?` or `Is there anything else you'd like me to help you with?`, and the statement
then keeps the tool. Keeping the tool is the safe direction of this refusal; the cost is a forget
call on a statement, which matches nothing and withholds the stated fact from memory. In six live
draws of `Hi! How are you today?` then `My locker code at the pool is 7319.`, every second request
listed the tool, four called it, and those four stored no locker row
([the draw](../../readings/forget-refusal-english-statement.md#a-statement-after-a-courtesy-question-what-was-drawn)).
`forget_unrequested("My alarm code is 5528.", "Got it. How was your day?")` keeps the tool.

## What to do

1. Write tests first: the statement after `How was your day?` and after `How can I help you
   today?` refuses the tool; after `Which code is it?` following `Cancel the code I gave you.`
   two turns back it keeps the tool.
2. Change the shape rather than the question check: keep the tool on a statement when a forget is
   still open in the chat (a person's message within the last two exchanges names forgetting), and
   refuse it otherwise, whatever the last reply asks.
3. Replay every recorded message and test string with its last replies, and draw the six chains
   above plus the forget flow on a brain built from the change.

## History

- 2026-11-13: filed by the second audit of the night, with the draws above.
