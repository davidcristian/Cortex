# A turn that goes quiet for an hour is indistinguishable from a brain that died

**Status:** open, a seam or port change comes first
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Verified:** 2026-09-13

Opened 2026-08-24 by the close of
[R-303](303-turn-stream-stall.md), which bounded the turn stream's silence and could only draw the
bound above the longest silence the brain legitimately produces.

That bound is four hours (`DEFAULT_TURN_IDLE_GAP_MS = 14_400_000`), and it is honest rather than
useful. It was sized by a delegated subtask, which waits for the CPU budget
(`DEFAULT_ADMISSION_WAIT_S`) and then runs under a deadline
(`DEFAULT_SUBAGENT_RUN_TIMEOUT_S`), emitting nothing at the seam through either stretch unless it
happens to call a tool. So the body cannot tell a brain working from a brain gone, and the overlay
shows a thinking indicator for both.

The bound grew on the way here, which is what makes this entry worth more than when it was filed.
The admission wait was 3600 s when the gap landed and is 7200 s now, raised the following day so a
queued spawn never stops waiting on a run still inside the time this deployment granted it, and
that grant is two run deadlines rather than one. The longest legitimate silence is therefore
12000 s, and the gap was resized to sit a fifth above it. Nothing about what this entry asks for
changed: every one of those hours is a turn the overlay cannot tell from a dead brain, and the
heartbeat is what would let the gap come down instead of being re-derived upward each time a
subagent bound moves.

The tightening that suggests itself is rejected for a reason worth keeping: the delegation does
emit a `StatusUpdate`, but progress travels on a best-effort sink that drops an event on
a saturated buffer by design (`cortex_core/progress.py`), so a decision that ends a turn must not
rest on having received one.

**What would close it.** A message the brain sends on a schedule, rather than an inference the
body makes. Two shapes, and the second is probably right:

- A periodic `StatusUpdate` on a long wait, refreshed rather than emitted once, which would let the
  idle gap fall to minutes. It has to travel a path that cannot drop it, which is the part that is
  not free: `ProgressSink.emit` is non-blocking by design so a slow overlay never delays real work,
  and a heartbeat that shares that property is a heartbeat that can go missing exactly when the
  buffer is full.
- A keepalive on the stream itself rather than in the turn's event vocabulary, which is a seam
  question (`proto/body.proto`) and would serve every future long stretch without each one needing
  an event of its own.

Either way the body's side is one line: the gap decorator already resets on any item, so a
heartbeat that reaches it costs nothing to consume. What the change buys, besides the number, is a
surface: the overlay could say what the turn is waiting for instead of showing the same indicator
for a model thinking, a subagent queued, and a brain that stopped existing.

**Why it was left.** The close was about giving the stall any bound at all, and it did. Making that
bound tight is a brain change and possibly a proto change, which is a different slice with a
different gate, and the trigger for it is the same one that never fired for the entry above: nobody
here has yet watched a turn stall.

## Trail

- 2026-09-13: Re-derived against the two constants the bound is drawn from and the seam. The
  rejected tightening still holds exactly as written: `ProgressSink.emit` drops on a saturated
  buffer by design (`cortex_core/progress.py`), and the proto declares no keepalive, `ServerEvent`
  carrying the same five event kinds it did when this was filed. The stall nobody has watched is
  still unwatched, so the entry stays open. What changed is underneath it: the admission wait moved
  from 3600 s to 7200 s the day after the gap landed, and the run bound counts twice rather than
  once, so the arithmetic quoted here was stale and the gap it justified is now shorter than the
  silence rather than longer. Corrected above, and the drift is written up in the ADR-0024
  addendum on the admission wait moving without the gap.
- 2026-09-13: The gap was resized to 14400000 ms and the numbers above were refreshed to match.
  The silence this entry describes is four hours now rather than two, and the brain-side coupling
  that would have caught the drift is in place, so the next move of a subagent bound reaches this
  bound as a gate failure.
