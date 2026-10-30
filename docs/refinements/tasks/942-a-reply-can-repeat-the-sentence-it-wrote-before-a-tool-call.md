# A reply can repeat the sentence it wrote before a tool call

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-30

`stream_tool_loop` (`tool_loop.py`) streams the text of every round to the person and joins the
rounds into the reply. A round that ends in a call keeps its text in the call message, so the next
round sees what it already said, and the model can still write it again. In one W04 draw of the
forget wordings ([readings](../../readings/forget-request-wordings.md#thirteen-more-wordings-the-draws-2026-10-30)),
"What's the capital of Australia? And forget my phone number 0612345678 while you're at it." made
the cortex write "The capital of Australia is Canberra." beside its `forget_memories` call, and the
next round began with the same sentence. The stream sent it twice, and the chat's stored assistant
message holds both. In a draw of 2026-10-29 that asked to remember a locker code and list the
readable folders, the reply said "I've remembered that your locker code is 7319." before and
after its directory listing. Across the recorded draws of 2026-10-29 and 2026-10-30, 2 of 407
turns that called a tool repeated their first sentence this way.

## What to do

1. Write rows that ask a question and request a tool in one message, such as W04, and the rule a
   change must pass, into the readings before drawing a baseline. Count the replies in which a
   sentence written before a call starts the text after it.
2. Prefer a typed check over a prompt rule: the loop holds a later round's first sentence until
   it ends, and drops it when the text already streamed holds it word for word. It changes what
   the person sees, so its tests include a reply that repeats a sentence on purpose later on.

## History

- 2026-10-30: filed from the forget wording draws, where one W04 reply repeated its first
  sentence (R-923).
