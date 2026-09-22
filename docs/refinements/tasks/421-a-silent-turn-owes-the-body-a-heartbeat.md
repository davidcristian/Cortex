# A turn that goes quiet for hours is indistinguishable from a brain that died

**Status:** done 2026-09-22
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The turn stream's silence is bounded at four hours (`DEFAULT_TURN_IDLE_GAP_MS = 14_400_000`), which
is accurate rather than useful. The bound is sized by a delegated subtask, which waits for the CPU
budget (`DEFAULT_ADMISSION_WAIT_S`) and then runs under a deadline
(`DEFAULT_SUBAGENT_RUN_TIMEOUT_S`), sending nothing over the connection through either stretch
unless it happens to call a tool. So the body cannot tell a brain working from a brain gone, and
the overlay shows a thinking indicator for both.

The bound grew after this was filed. The admission wait was 3600 s when the gap was added and is
7200 s now, raised so a queued spawn never stops waiting on a run still inside the time this
deployment granted it, and that grant is two run deadlines rather than one. The longest legitimate
silence is therefore 12000 s, and the gap was resized to sit a fifth above it. A heartbeat is what
would let the gap come down instead of being recomputed upward each time a subagent bound moves.

The obvious tightening is rejected for a reason worth keeping: the delegation does send a
`StatusUpdate`, but progress travels on a best-effort sink that drops an event on a full buffer by
design (`cortex_core/progress.py`), so a decision that ends a turn must not depend on having
received one.

**What would close it.** A message the brain sends on a schedule, rather than an inference the body
makes. Two shapes, and the second is probably right:

- A periodic `StatusUpdate` on a long wait, refreshed rather than sent once, which would let the
  idle gap fall to minutes. It has to travel a path that cannot drop it, which is the part that is
  not free: `ProgressSink.emit` is non-blocking by design so a slow overlay never delays real work,
  and a heartbeat with that property can go missing exactly when the buffer is full.
- A keepalive on the stream itself rather than in the turn's event vocabulary, which is a change to
  `proto/body.proto` and would serve every future long stretch without
  each one needing an event of its own.

Either way the body's side is one line: the gap decorator already resets on any item. What the
change buys, besides the number, is that the overlay could say what the turn is waiting for instead
of showing the same indicator for a model thinking, a subagent queued, and a brain that stopped
existing.

## History

- 2026-08-24: opened by the close of [R-303](303-turn-stream-stall.md), which bounded the turn
  stream's silence and could only set the bound above the longest silence the brain legitimately
  produces.
- 2026-09-13: checked against the two constants the bound is drawn from and against the interface.
  The rejected tightening still holds exactly as written: `ProgressSink.emit` drops on a full
  buffer by design, and the proto declares no keepalive. Nobody has yet watched a turn stall, so
  the entry stays open. What changed is underneath it: the admission wait moved from 3600 s to
  7200 s the day after the gap was added, and the run bound counts twice rather than once, so the
  arithmetic quoted here was stale and the gap it justified was shorter than the silence rather
  than longer. Corrected above.
- 2026-09-13: the gap was resized to 14400000 ms and the numbers above were refreshed to match.
  The silence is four hours now rather than two, and the brain-side coupling that would have caught
  the mismatch is in place, so the next move of a subagent bound makes this bound fail a check.
- 2026-09-19: checked again. The interface change has not happened: `proto/body.proto` declares no
  keepalive or heartbeat, no port has one, and the only mention of a heartbeat in the code is the
  comment on `DEFAULT_TURN_IDLE_GAP_MS` (`body/crates/core/src/retry/gap.rs`) saying the gap needs
  one to come down. The arithmetic holds: `DEFAULT_ADMISSION_WAIT_S` is 7200.0
  (`cortex_core/scheduler.py`), `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` is 2400.0
  (`cortex_core/subagents.py`), 7200 plus two runs of 2400 is 12000 s, and a fifth above that is
  the shipped 14400000 ms. `ProgressSink.emit` still drops on a full buffer by design. One count in
  the first 2026-09-13 entry was wrong: `ServerEvent` has eight event kinds, `text_delta` through
  `tool_outcome`, not five, and it already had eight when this entry was filed, `tool_outcome`
  having shipped on 2026-08-06. Nothing the entry argues rests on that number.
- 2026-09-22: done, as [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md). The shape is the second
  one above, a proto change: a `Heartbeat` in `ServerEvent`'s oneof, sent by the `Converse`
  stream's own task rather than by the turn or through `ProgressSink`, every 30 s while a turn task
  runs and the output queue is empty, with a buffer credit, so it is never dropped. The claim that the body's side is one line
  was wrong. Letting a heartbeat restart the idle gap would have removed the only bound on a turn
  stuck on a live brain, so the body adds a two-minute gap on the stream's silence and counts each
  heartbeat as 30 s of the turn's own, which keeps the ten-minute and four-hour bounds. HTTP/2
  keepalive was rejected because gRPC's C core answers a ping while the Python event loop is
  blocked. Opened [R-708](708-the-overlay-cannot-say-what-a-turn-waits-for.md) for the overlay
  label this entry mentions.
