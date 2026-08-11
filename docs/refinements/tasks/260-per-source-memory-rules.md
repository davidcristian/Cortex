# Per-source memory rules for vision turns

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** unrecorded

Per-source memory rules, so a vision turn can be remembered deliberately. An opaque turn is
dropped from durable memory outright, which is the safe default and a blunt one: "remember that
my invoice number is 4021" after a capture is lost. A per-source policy (this source may be
recorded, that one may not) is the general fix, and it belongs with the per-provenance rules
already recorded under [untrusted-content.md](../index.md#untrusted-content).

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, one of four vision entries the
  index grouped in its fix-when-it-bites bucket with the trigger its own entry implies, and the one
  it read as riding the per-provenance eviction entry in untrusted content rather than standing
  alone. The index dates that grouping only as "the same day" beside a paragraph about entries that
  had no bucket line until 2026-07-19, so which of the two days it means is not settled there.
- 2026-08-09: covered by the trigger sweep that ran against the tree over the whole fix-when-it-bites
  bucket and fired nothing. The index recorded that sweep so the next reader would spend the pass
  elsewhere instead of re-deriving the same verdicts, and it read every entry in the bucket against
  the code rather than against the entry's own text.
