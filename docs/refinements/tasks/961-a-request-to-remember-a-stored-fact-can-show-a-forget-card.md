# A request to remember a stored fact can show a forget card

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

With one stored exchange holding the fact, a request to remember that same fact called
`forget_memories` and showed a forget card in 1 of 12 draws on the shipped build
([readings](../../readings/unasked-tools-listed-on-remember.md#the-draws-2026-10-31)). The approved
card deleted the stored row and the turn was kept out of memory, so the person who asked to remember
the fact lost it. A denied card keeps the old row and drops the new exchange. With an empty pool the
same calls match nothing and do no harm, 4 of 15 draws on the shipped build.

Listing `set_volume` and `schedule_task` and refusing a call by name was this task's first idea. It
drew 5 of 15 calls and 3 of 12 cards against 4 of 15 and 1 of 12, so it did not ship.

## What to do

1. Write rows and a rule, with the S rows of that record among them, for refusing `forget_memories`
   by name when `asks_kept` reads the message and `asks_not_kept` does not. A refused call must not
   count in `TaintLedger.name_forget`, or the turn is still kept out of memory.
2. Near misses come first, and every wording of a request to forget must keep the tool, since a forget
   that cannot run is worse than a card. The rows W01, W06 and P01 of
   [forget-no-match-on-remember.md](../../readings/forget-no-match-on-remember.md) go in the rule.
3. Before citing the separated pair again, record the first request of `6b9956582` and of a build that
   lists both tools and compare them. The pair's "before" drew 1 of 30 and a build listing the same
   tools drew 5 of 15.

## History

- 2026-10-31: filed from the separated pair of
  [R-952](952-withheld-unasked-tools-may-raise-forget-calls-on-a-remember-request.md).
- 2026-10-31: corrected and retitled from "Leaving tools out of a request to remember raises forget
  calls". The candidate that lists both tools failed its rule, which also drew the seeded pool for the
  first time.
