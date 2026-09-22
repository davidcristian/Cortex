# The overlay cannot say what a turn is waiting for

**Status:** open, needs a port change first
**Area:** body-overlay
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md)
**Verified:** 2026-09-22

While a turn runs, the overlay shows one thinking indicator for a model generating, a subagent
queued for admission, a model loading during a swap, and a tool call in progress. The brain now
sends a `Heartbeat` every 30 s of a quiet turn ([ADR-0069](../../adr/ADR-0069-turn-heartbeat.md)),
but the message is empty and the body consumes it in `within_gaps`, so nothing about the wait
reaches the webview.

The `StatusUpdate` events that do name a wait (`delegating`, a model swap) travel the best-effort
`ProgressSink`, which drops an event when the buffer is full, so the overlay cannot rely on having
the latest one.

**What would close it.** Three parts, in this order:

- The brain keeps a record of what the running turn is waiting on, set where each wait begins (the
  admission queue in `cortex_core/scheduler.py`, a swap, an inference call, a tool dispatch, a
  confirmation) and cleared where it ends. That is new state the orchestrator keeps for the life
  of the turn, never inside a model process.
- `Heartbeat` gains a field naming that wait, and the body passes it on to the overlay instead of
  discarding it.
- A designed set of labels for the waits. This is a naming decision for the maintainer (AGENTS.md
  "Names are designed"), with a recommended set and alternatives proposed before any is chosen.

## History

- 2026-09-22: opened by the close of
  [R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md), which added the heartbeat without
  anything for the overlay to show.
