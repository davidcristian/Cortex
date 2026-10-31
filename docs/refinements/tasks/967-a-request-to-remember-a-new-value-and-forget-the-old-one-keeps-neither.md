# A request to remember a new value and forget the old one keeps neither

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`Note that my phone number is now 0699000000, and delete the old one.` showed a card in 7 of 8 draws.
The approved card deleted the old row and the turn stayed out of memory, so no row held either number
([rows](../../readings/forget-refused-on-remember.md#the-draws-2026-10-31), row M02). Four replies said the number was updated, for
example "I've updated my records to reflect that your new phone number is 0699000000", with no
`UNKEPT_CLAIM_NOTE`, since `claims_kept` (`memory_claim.py`) does not read that wording. A draw of
`Remember that my new locker code is 8426, and forget the old code.` with no call said "I've noted your
new locker code as 8426 and have forgotten your previous code." The old row stayed, and
`claims_forgotten` (`forget_claim.py`) does not read "and have forgotten".

## What to do

1. Decide whether a card whose row does not hold the new value can leave the new value recorded.
   ADR-0075 keeps the turn out because its text may name what was forgotten, so the rows need the new
   value and the old value apart.
2. Near-miss tests first if `claims_kept` is widened to read "updated my records" or
   `claims_forgotten` to read "and have forgotten".

## History

- 2026-10-31: filed from the rows of the check of refusing a forget call.
