# Turning the recap on by default

**Status:** landed 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**The default moved to on, 2026-08-06, on the user's standing decision now carried by numbers
([ADR-0038 cheap-fold addendum](../../adr/ADR-0038-ranked-recall.md)).** The previous pass refused
to ship it over its numbers; these are the numbers that let it ship on them. **Retention moved
from 2 of 3 to 3 of 3** over the same three staged sessions of five compounding folds, and the
final accounts now carry the reference, the hotel, the card, the adapter, the museums and the
transit advice together instead of keeping recent filler. A fold costs 2.9 s to 6.2 s with a
chip on screen saying why, against 14.5 s to 224.5 s in silence. At the shipped floor the same
conversation folded **once** over five boundary moves for 3.4 s of model time in total, still
3 of 3. `CORTEX_HISTORY_SUMMARY=false` is the same one switch it always was, pointing the other
way, and the new default is pinned by a test that reddens when it is flipped back. **What the
run also showed honestly:** at the floor, the account covered 10 of the 20 dropped messages and
the other 10 sat in neither the window nor the account, under the floor, which is the gap the
budget clamp exists to bound. Remaining from this deferral: nothing of its own; the one-corpus
entry above is now the only thing between this feature and a claim about real conversations.
