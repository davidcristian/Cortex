# A forget of the old value can match nothing and say none is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`Note that my phone number is now 0699000000, and delete the old one.`, with a row holding
`0612345678`, called `forget_memories` with a text that matched nothing in 3 of 22 draws of it and its
locker code form. The old row stays and the turn is stored, so two rows hold different numbers. Each
reply said no old value was stored, for example "I couldn't find a previous phone number to remove as
there wasn't one stored" ([draws](../../readings/claim-reader-replays.md#the-readers-in-real-turns-2026-10-31)),
since `_NONE_FOUND` (`memory_forget_chosen.py`) tells the model to say nothing about it was stored.

The texts of those calls are not recorded: no card shows on a call that matches nothing, and the audit
keeps the argument as `<redacted>`. That they were words such as "old code" is an assumption from the
replies.

## What to do

1. Record the requests with `slot1/proxy.py` from the 2026-10-31 scratchpad, and read the texts.
2. If they are words no row holds, write rows and a rule for a result text that asks for one word
   naming the fact. `_NONE_FOUND` is shared with a forget of a value never stored, where "nothing about
   it was stored" is correct, so both rows are drawn.

## History

- 2026-10-31: filed from the draws of the fixed readers of
  [R-967](967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md).
