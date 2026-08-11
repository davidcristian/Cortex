# A cost-aware batch cap

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Trigger:** Roster entries differ enough that eight of one is not eight of another.

This item has no bullet of its own in the area doc. It was recorded inside the entry for the batch
cap on `spawn_subagents`, in the list of items remaining behind the same tool:

> a **cost-aware batch** (a cap in placements or estimated VRAM rather than in items) if roster
> entries ever differ enough that eight of one is not eight of another

The cap it would replace counts items: "`MAX_SPAWN_BATCH = 8` ... **refuses** an oversized batch
rather than truncating it", each subagent in a batch being "an admission slot, a placement, and an
inference".

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index names the salience and batch-cap knobs among the entries whose trigger is a
  deployment doing something rather than a file saying something, so no reading of the code settles
  them.
