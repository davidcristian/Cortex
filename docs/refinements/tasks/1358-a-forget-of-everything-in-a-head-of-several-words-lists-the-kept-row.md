# A forget of everything in a head of several words lists the kept row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

A forget of everything whose head holds more than one word before a kept row with no clause mark
lists that row: `Forget all of it the card stays.`, `Forget it all the card stays.` and `Forget
the lot the card stays.` delete the card for the call texts `card` and `4242`. Over the audit's
mixed messages, 18 of 2,316 rows asked to keep are listed, all after `Forget all of it`
([readings](../../readings/forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).
`_head_run` (`forget_permit.py`) reads the run after one unread first word only, and reads
nothing when a placing word, as `of` or `on`, follows that word. The same heads with a comma
before the row keep it.

## What to do

1. Find one rule that keeps the row after every head of this kind, counted over `gen.py` and
   `probe.py` in `~/.cache/cortex-run/2026-11-26/a1/` and the f1 family, and state its cost as the
   rows asked to delete that it newly keeps. A word list of heads is not added.
2. Build it when that cost is stated, or decline the task with the count.
3. Replay with `replay.sh` and `cmp.py` in that directory against the tree before the change.

## History

- 2026-11-26: filed from the audit replay of `_head_run`, which keeps every row of the one word
  heads it was built for.
