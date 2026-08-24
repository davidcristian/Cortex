# A turn that goes quiet for an hour is indistinguishable from a brain that died

**Status:** open, a seam or port change comes first
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Opened 2026-08-24 by the close of
[R-303](303-turn-stream-stall.md), which bounded the turn stream's silence and could only draw the
bound above the longest silence the brain legitimately produces.

That bound is two hours, and it is honest rather than useful. It is sized by a delegated subtask,
which waits up to `DEFAULT_ADMISSION_WAIT_S` (3600 s) for the CPU budget and then runs up to
`DEFAULT_SUBAGENT_RUN_TIMEOUT_S` (2400 s), emitting nothing at the seam through either stretch
unless it happens to call a tool. So the body cannot tell a brain working from a brain gone, and
the overlay shows a thinking indicator for both.

The tightening that suggests itself is refused for a reason worth keeping: the delegation does
announce itself with a `StatusUpdate`, but progress rides a best-effort sink that drops an event on
a saturated buffer by design (`cortex_core/progress.py`), so a decision that ends a turn must not
rest on having received one.

**What would close it.** Something the brain owes rather than something the body guesses. Two
shapes, and the second is probably right:

- A periodic `StatusUpdate` on a long wait, refreshed rather than emitted once, which would let the
  idle gap fall to minutes. It has to travel a path that cannot drop it, which is the part that is
  not free: `ProgressSink.emit` is non-blocking by design so a slow overlay never delays real work,
  and a heartbeat that shares that property is a heartbeat that can go missing exactly when the
  buffer is full.
- A keepalive on the stream itself rather than in the turn's event vocabulary, which is a seam
  question (`proto/body.proto`) and would serve every future long stretch without teaching each one
  to announce itself.

Either way the body's side is one line: the gap decorator already resets on any item, so a
heartbeat that reaches it costs nothing to consume. What the change buys, besides the number, is a
surface: the overlay could say what the turn is waiting for instead of showing the same indicator
for a model thinking, a subagent queued, and a brain that stopped existing.

**Why it was left.** The close was about giving the stall any bound at all, and it did. Making that
bound tight is a brain change and possibly a proto change, which is a different slice with a
different gate, and the trigger for it is the same one that never fired for the entry above: nobody
here has yet watched a turn stall.
