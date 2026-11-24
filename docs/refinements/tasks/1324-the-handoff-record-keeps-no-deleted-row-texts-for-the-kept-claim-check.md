# The handoff record keeps no deleted row texts for the kept claim check

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

`kept_claim` (`forget_kept_sentence.py`) marks a reply only while `TaintLedger.forget_gone`, the
texts of the turn's deleted rows, covers `TaintLedger.forget_deleted`, since a word of a deleted
row must name no kept row. `HandoffRecord` (`handoff.py`) and its codec keep `forget_deleted` and
`forget_kept` but not `forget_gone`, so after a handoff whose cortex phase deleted a row the deep
model's reply keeps the plain kept note, whatever it says. That is the safe direction, and it
leaves those turns unread.

What would close it: `forget_gone` in `HandoffRecord`, `handoff_codec.py` and the handoff store
contract test, with a record written before the field read back as an empty tuple, and a deep
phase test whose reply names a kept row as forgotten after a cortex phase delete.

## History

- 2026-11-24: filed with the check that marks a reply naming a kept row as forgotten.
