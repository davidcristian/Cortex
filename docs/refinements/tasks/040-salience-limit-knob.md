# A limit knob for the salience policy

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** Two proves wrong as the repeat limit.

This item has no bullet of its own in the area doc. It was recorded inside the entry for salience
on the tool loop, in the list of items remaining behind the same seam:

> **a limit knob** if two proves wrong

The limit it would make configurable is the one `RepeatSalience` ships: it "admits a call unless
an identical one (same `name` and `arguments`) already ran **in this round**, or already ran
**twice in this loop**", and two was chosen over one because "refusing at one denies information
(the re-read after a write returns the stale listing), allowing two wastes at most one dispatch,
and preferring the benign failure is the ADR-0025 clamp's argument again".

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index names the salience and batch-cap knobs among the entries whose trigger is a
  deployment doing something rather than a file saying something, so no reading of the code settles
  them.
