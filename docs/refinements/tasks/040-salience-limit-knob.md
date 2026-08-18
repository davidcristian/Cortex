# A limit knob for the salience policy

**Status:** landed 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

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
- 2026-08-18: became `CORTEX_TOOLS_SALIENCE_LIMIT`, a `ToolsConfig.salience_limit` field
  defaulting to the core's `MAX_IDENTICAL_DISPATCHES` that `salience_policy` builds
  `RepeatSalience(limit=...)` from. Closed without waiting for the trigger because the trigger was
  never what the work needed: the origin decision record's own remaining list named the env var
  and called it config rather than design, the policy's `limit` parameter and its non-positive
  rejection already shipped, and the only escape hatch a deployment had was binary (`repeat` or
  `off`, where `off` deletes the bound), so nothing between two and unbounded could be expressed.
  A value below 1 now fails at boot; there is deliberately no ceiling, argued in the addendum,
  since a large limit never binds and still keeps the once-per-round clause that `off` drops. The
  compose default is tied to the core constant in `scripts/couplings.py`. Opened
  [306](306-subagent-memory-budget-spelled-twice.md), the untied neighbour that survey found.
