# A deep phase counts an earlier unmatched forget as a delete

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`unforgotten_claim` (`forget_claim.py`) appends `UNFORGOTTEN_CLAIM_NOTE` to a reply that says
something was forgotten when no forget call of the turn deleted a memory, and it reads the
`forget_memories` runs that matched nothing from `TaintLedger.forget_unmatched`. The deep phase
rebuilds its ledger from the handoff record (`HandoffRecord.taint_ledger` in `handoff.py`), which
keeps `forget_asked` but not `forget_unmatched`. A cortex `forget_memories` call that matched
nothing before a handoff is then one of the `earlier` runs that `ok` and is not counted as
unmatched, so the deep reply's "I have removed it from my memory" gets no note though nothing was
deleted. The default stack has no deep tier and no escalation, so no draw has reached this.

## What to do

1. Keep `forget_unmatched` (and `forget_calls`, which `memory_withheld` reads the same way) in the
   handoff record and its codec (`handoff_codec.py`), restore them in `taint_ledger`, and add a
   brain phase test whose cortex forget matched nothing and whose deep reply claims a removal.

## History

- 2026-10-30: filed when the check of a removal claimed with no forget call was built; the gap is
  written in [brain-core-memory.md](../../modules/brain-core-memory.md).
