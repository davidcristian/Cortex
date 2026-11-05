# A forget of the old value can match nothing and say none is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-05

`Note that my phone number is now 0699000000, and delete the old one.`, with a row holding
`0612345678`, called `forget_memories` with a text that matched nothing in 3 of 22 draws of it and its
locker code form. The old row stays and the turn is stored, so two rows hold different numbers. Each
reply said no old value was stored, for example "I couldn't find a previous phone number to remove as
there wasn't one stored" ([draws](../../readings/claim-reader-replays.md#the-readers-in-real-turns-2026-10-31)),
since `_NONE_FOUND` (`memory_forget_chosen.py`) tells the model to say nothing about it was stored.
One more such draw said the new code "was not kept because you asked to forget something in the same
message" while a row held it
([draw](../../readings/claim-reader-replays.md#the-note-on-every-withheld-request-to-remember-the-draws-2026-10-31)).

A second form was drawn on 2026-11-05
([draws](../../readings/forget-no-match-on-remember.md#the-texts-of-the-forget-calls-on-a-new-value-2026-11-05)):
the turn called the forget twice with the old value. The first call's card deleted the row, the
second call matched nothing, and the reply said the old number "appears it was already gone". The
no-match result is true of the store when the second call runs and false of the turn.

The texts of the 2026-10-31 calls are not recorded: no card shows on a call that matches nothing, and
the audit keeps the argument as `<redacted>`. That they were words such as "old code" is an assumption
from the replies. The 2026-11-05 draws read every text through a proxy that records the requests to
the model host, and no first call matched nothing, so the assumption stands.

## What to do

1. The second form first, because a typed result can be true by construction. `ForgetChosenTool`
   keeps the texts whose card it ran a delete for, under the call's turn id and bounded as `_shown`
   is. A later call in the same turn whose text matches nothing and equals one of them, with case and
   spaces ignored, gets "nothing more was forgotten: an earlier call in this turn already deleted
   every remembered exchange that contained that text", not `_NONE_FOUND`. The rows and the rule are
   [written](../../readings/forget-no-match-on-remember.md#a-repeated-forget-rows-and-the-rule-2026-11-05)
   before any draw.
2. Record the texts with the proxy whenever M02 is drawn. If an unmatched first call names a word no
   row holds, write rows and a rule for a result text that asks for one word naming the fact.
   `_NONE_FOUND` is shared with a forget of a value never stored, where "nothing about it was stored"
   is correct, so both rows are drawn.

## History

- 2026-10-31: filed from the draws of the fixed readers of
  [R-967](967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md).
- 2026-11-05: the premise holds in the code: a run that matches nothing returns `_NONE_FOUND` with no
  card, and `_unmatched_keep` (`memory_claim.py`) stores the turn when every forget call matched
  nothing and `asks_kept` reads the message. Ten draws of M02 read every call text, found the
  repeated forget, and found no unmatched first call; the first step and its rule are written.
