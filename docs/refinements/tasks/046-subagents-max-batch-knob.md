# A `CORTEX_SUBAGENTS_MAX_BATCH` knob

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Trigger:** A host wants a ceiling other than the shipped eight.

This item has no bullet of its own in the area doc. It was recorded inside the entry for the batch
cap on `spawn_subagents`, in the list of items remaining behind the same tool:

> a **`CORTEX_SUBAGENTS_MAX_BATCH` knob** if a host ever wants a different ceiling

The ceiling it would make configurable is the one the batch cap ships: "`MAX_SPAWN_BATCH = 8` (a
constant beside `MAX_TOOL_DISPATCHES`, since how many subtasks one *call* may ask for is policy,
while what the host runs *concurrently* is the deployment fact the CPU-budget env already tunes)".

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index names the salience and batch-cap knobs among the entries whose trigger is a
  deployment doing something rather than a file saying something, so no reading of the code settles
  them.
