# Turning the recap on by default

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The default moved to on once the numbers supported it. Retention moved from 2 of 3 to 3 of 3 over
the same three staged sessions of five compounding folds, and the final accounts now contain the
reference, the hotel, the card, the adapter, the museums and the transit advice together instead
of keeping recent filler. A fold costs 2.9 s to 6.2 s with a chip on screen saying why, against
14.5 s to 224.5 s with nothing on screen. At the shipped floor the same conversation folded once
over five boundary moves for 3.4 s of model time in total, still 3 of 3.
`CORTEX_HISTORY_SUMMARY=false` is the same single switch it always was, pointing the other way,
and the new default is asserted by a test that fails when it is changed back.

The run also showed the cost: at the floor, the account covered 10 of the 20 dropped messages and
the other 10 sat in neither the window nor the account, which is the gap the budget clamp exists
to bound. [R-029](029-one-corpus-recap-measurement.md) is now the only thing between this feature
and a claim about real conversations.
