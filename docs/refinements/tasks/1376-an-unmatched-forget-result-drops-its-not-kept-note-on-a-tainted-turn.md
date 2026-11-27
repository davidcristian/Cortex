# An unmatched forget result drops its not kept note on a tainted turn

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-27

`dispatch` leaves `FORGET_NOT_KEPT_NOTE` off the result of a forget call that matched nothing on
a statement `opened_earlier` reads (`keeps_unmatched`, `forget_opened_earlier.py`), since such a
turn is recorded. A tainted turn under the default `skip` policy is still withheld by
`memory_withheld`, so on it the model is not told that nothing in the message is kept. Over 40
generated tainted turns of that shape with `record_tainted_memory` off, all 40 were withheld with
the note left off. A reply on such a turn that claims the fact was noted still ends with
`UNKEPT_CLAIM_NOTE`, so the person is told; the cost is a claim corrected rather than avoided.

## What to do

1. Decide whether `keeps_unmatched` reads the call's `TurnStamp.tainted`. The dispatcher does
   not know the taint policy, so under `record` the note would then be false on a recorded turn.
2. Test both policies: the note is on every result of a turn memory does not store, and on none of
   a turn it stores.

## History

- 2026-11-27: filed from the audit of the change that stores a statement after a forget opened by
  an earlier turn (`~/.cache/cortex-run/2026-11-27/a1/`, `note0.py`).
