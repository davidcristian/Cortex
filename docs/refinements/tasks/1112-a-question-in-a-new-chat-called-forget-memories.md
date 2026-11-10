# A question in a new chat called forget_memories

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

In c1 draw 4 of [the readings](../../readings/correction-keeps-old-value.md), after a correction turn had deleted the only bike lock row, `What is my bike lock
code?` in a new chat called `forget_memories` (its text is redacted in the audit log). The call
matched nothing, so the reply `I don't have your bike lock code in my memory.` ended with
`UNMATCHED_FORGET_NOTE`, which tells the person about a forget they never asked for. One of 18
question turns; no card showed, so nothing was deleted.

## What to do

1. Draw the question in a new chat with no row and with one row, 8 times each, recording the call
   text through the proxy, before deciding anything.
2. If the call repeats, weigh a typed refusal of a forget on a turn whose message holds no forget
   verb against a change to the tool description. A refusal keeps the tool usable on every message
   that does ask to forget.

## History

- 2026-11-10: filed from c1 draw 4 in [the readings](../../readings/correction-keeps-old-value.md).
