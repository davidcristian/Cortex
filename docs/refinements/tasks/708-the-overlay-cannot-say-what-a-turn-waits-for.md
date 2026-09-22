# The overlay cannot say what a turn is waiting for

**Status:** open, needs a port change first
**Area:** body-overlay
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md)
**Verified:** 2026-09-22

While a turn runs, the overlay shows a status chip holding the sentence of the latest
`StatusUpdate`, and a tool chip naming the tool being called. Two things are missing from that. A
delegation sends its `delegating` sentence once, before its subtasks wait for room in the subagent
budget (`cortex_core/spawn.py`), so a subtask queued for up to `DEFAULT_ADMISSION_WAIT_S` (7200 s)
reads the same as one running. And a `StatusUpdate` travels the best-effort `ProgressSink`, which
drops an event when its buffer is full, so the chip can show a wait that has ended. The brain now
sends a `Heartbeat` every 30 s of a quiet turn ([ADR-0069](../../adr/ADR-0069-turn-heartbeat.md)),
but the message is empty and the body consumes it in `within_gaps`, so nothing about the wait
reaches the webview.

**Proposed names**, for the maintainer to pick, checked against the code on 2026-09-22.

- **Plain verbs**, recommended. The wait field holds one of seven lowercase words, five of which
  the brain already sends as `StatusUpdate.state`: `thinking` (the model is generating), `queued`
  (a subtask waits for room in the subagent budget), `delegating` (subtasks are running),
  `swapping` (the deep model is loading, or the cortex is coming back), `folding` (the earlier
  conversation is being summarized), `calling` (a tool call is running) and `asking` (a confirm
  card waits for the user's answer). The chip keeps showing a sentence the brain writes, so the
  words are keys a user never reads alone. Each starts with its own letter, and `queued` appears
  nowhere in the code. The console's names already keep verbs as verbs where a string is read at
  a glance (Summon, Dismiss), and a status chip is such a string. `forgoing` is left out, because
  it is a note about the turn rather than a wait.
- **Directions of attention.** A designed family ordered by how far from the cortex the work is:
  Inward (the cortex generating), Aside (a subagent), Deeper (the deep model), Outward (a tool) and
  Yours (the user's answer). The order says where the work went, and no word collides with the
  mark's movements of thought. The cost is that Aside covers a queued subtask and a running one
  alike, which is the distinction this task exists to make, and a chip reading Aside needs the
  brain's sentence beside it.
- **No vocabulary.** The heartbeat repeats the latest status sentence as free text. It is the
  smallest change to the proto, but the overlay could then neither style nor order a wait, the
  limit [R-320](320-one-detail-string-two-facts.md) records for `HealthReply.detail`.

**What would close it.** The maintainer's pick, then three parts, in this order:

- The brain keeps a record of what the running turn is waiting on, set where each wait begins (the
  admission queue in `cortex_core/scheduler.py`, a swap, an inference call, a tool dispatch, a
  confirmation) and cleared where it ends. That is new state the orchestrator keeps for the life
  of the turn, never inside a model process.
- `Heartbeat` gains a field naming that wait, and the body passes it on to the overlay instead of
  discarding it.
- The overlay's chip reads the wait from the latest heartbeat, so a dropped `StatusUpdate` is
  corrected within one heartbeat period.

## History

- 2026-09-22: opened by the close of
  [R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md), which added the heartbeat without
  anything for the overlay to show. Three name sets are proposed above; the pick is the
  maintainer's.
