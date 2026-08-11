# A fair-share policy across a batch

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** Starvation shows up in practice.

One greedy subagent can spend the turn's remaining pool
before its siblings charge anything. Starvation degrades an answer without breaching the bound
(the starved subagent reads the refusal and reports stopping short), so it stays deferred until
it shows up in practice.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. Everything left open in that bucket is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
