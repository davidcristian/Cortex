# A round can repeat more than one sentence of an earlier round

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-30

`OpeningHold` (`round_opening.py`) drops the first sentence of a tool loop round when an earlier
round of the reply streamed it word for word, and streams the rest of the round. When the cortex
repeats two sentences, only the first is dropped. In one seeded W04 draw of the check of a
removal claimed with no forget call
([readings](../../readings/forget-request-wordings.md#a-removal-claimed-with-no-forget-call-the-candidate-2026-10-30)),
the first round wrote "The capital of Australia is Canberra. I have also removed the phone number
0612345678 from my memory as you requested." beside its `forget_memories` call; the reply shows
the second sentence twice, which fits a second round that began with both sentences. The rows of
[reply-repeat-across-a-tool-call.md](../../readings/reply-repeat-across-a-tool-call.md) count
only the round's first sentence.

## What to do

1. Write a row whose first round writes two sentences before its call, and a rule counting the
   replies that show any sentence twice, into the readings before a baseline.
2. Keep holding while each opening sentence is one an earlier round streamed, dropping each, and
   stream from the first sentence that is new; its tests keep a repeated sentence that follows a
   new one.

## History

- 2026-10-30: filed when the loop began dropping a repeated opening sentence.
