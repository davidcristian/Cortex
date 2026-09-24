# ADR-0069: The turn stream's heartbeat

**Status:** Accepted (2026-09-22)

## Context

[ADR-0024](ADR-0024-transport-retry.md) decisions 18 to 20 bound a turn by its silence: ten
minutes before its first event and four hours between two of them. The four hours is sized by a
delegated subtask, which may wait 7200 s for admission and then run twice for 2400 s without the
stream sending anything. So a brain that stopped mid turn was reported after up to four hours, and
until then the overlay showed the same thinking indicator it shows for a working turn.

Some failures reach the body without any help. A brain process that exits has its sockets closed
by the kernel, so the body's read of the stream fails and the adapter reports the error at once. A
connection the far side resets fails the same way. What sends nothing at all is:

- **a path that stops delivering without a reset**: a suspended host or virtual machine, a paused
  container, or a proxy in the path (Docker Desktop's port forwarding, WSL's mirrored networking)
  that keeps the body's side of the connection open after the far side is gone;
- **a brain whose event loop is blocked**, where the process and its sockets are alive and nothing
  is scheduled;
- **a turn task waiting on something that never happens**, on a loop that is otherwise running.

The first two can only be told apart from a slow turn by something the brain sends while it works.
The third needs a bound on the turn's own progress, which ADR-0024's gaps already are.

## Decision

1. **The brain sends a `Heartbeat` on the turn stream.** `ServerEvent.heartbeat` (field 9 in
   [proto/body.proto](../../proto/body.proto)) holds the turn's current wait (decision 7) and no
   turn content. One task per `Converse` stream,
   `ConverseStream._beat` (`cortex_orchestrator/converse_stream.py`), started and cancelled with the
   stream's pump, waits `HEARTBEAT_PERIOD_MS` (30000) through the core's `Sleeper` port and then
   sends one heartbeat **if a turn task is running and the output queue is empty**. So a heartbeat
   states four facts: the brain process runs, its event loop runs, this stream is still served,
   and one of its turns has not ended. It says nothing about whether that turn is making progress,
   which decision 4 bounds.

2. **It cannot be dropped, and it never queues behind other events.** It does not use the
   `ProgressSink`, which drops an event when the buffer is full. It is put on the stream's output
   queue with a buffer credit, like the turn's own events, and an empty queue means every credit is
   free, so taking one never waits. When the queue is not empty, no heartbeat is sent: events are
   already waiting, and the body's clock restarts on those. At most one heartbeat is ever queued.
   No new port is needed: the only effect is time, which the existing `Sleeper` port provides,
   with `AsyncioSleeper` in production and a fake in `tests/test_converse_heartbeat.py` that ends
   each wait when the test says so.

3. **The body bounds the stream's silence at four periods.** `TurnEvent::Heartbeat { wait,
   detail }` is the port's form of it; `BrainRpcClient` maps it, `within_gaps` counts it and
   passes it on, and the shell's `converse` command forwards it to the webview. A third
   gap, `TurnGaps::heartbeat`, is the longest the stream may send nothing at all, a heartbeat
   included: `DEFAULT_TURN_HEARTBEAT_GAP_MS` (120000), set by
   `CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS`. A live brain sends something at least once a period, so
   four periods lets a heartbeat run up to three periods late, which is an event loop blocked for
   about 90 s, before the body gives up. The expiry is the same `Timeout { after }` as any gap
   (ADR-0024 decision 21): the reply keeps what arrived, and the header dot goes red with
   `no reply within 120s`.

4. **The turn's own gaps stay, counted in heartbeats.** `first` (ten minutes) and `idle` (four
   hours) still bound the turn's silence, meaning the time with no event other than a heartbeat.
   The core has no clock to read, so each heartbeat counts as one period (`TurnGaps::period`, the
   body's copy of `HEARTBEAT_PERIOD_MS`), and the turn ends with `Timeout { after }` naming `first`
   or `idle` once the count reaches it. Every poll of the stream is bounded by the heartbeat gap or
   by what is left of the turn's allowance, whichever is shorter. A stream with no heartbeats
   therefore runs under exactly the bounds ADR-0024 describes, and `TurnGaps::UNBOUNDED` counts a
   heartbeat as nothing. The decisions stay in the non-generic `GapClock`, so the generic stream
   has no new branch (ADR-0024's reason for that struct).

5. **The period is written twice and checked once.** `HEARTBEAT_PERIOD_MS` is declared in
   `body/crates/core/src/retry/gap.rs` and in `converse_stream.py`, and
   `scripts/wirecouplings.py` makes `crosscheck` fail when the two differ. `retry_gap.rs` asserts
   that the shipped heartbeat gap is four periods and shorter than the first-event gap. The period
   is not a setting: the body counts heartbeats with its own copy, so a setting on one side would
   need the same value set on the other by hand.

6. **Body and brain are upgraded together.** An older body decodes a heartbeat as a
   `ServerEvent` with no event set, which its adapter reports as a protocol error that ends the
   turn. An older brain sends no heartbeats, so a newer body ends every turn silent for two
   minutes; setting `CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS` to the idle gap restores ADR-0024's
   behaviour until the brain is rebuilt.

7. **A heartbeat says what the turn waits on.** `Heartbeat` has `wait`, a key, and `detail`, the
   sentence the overlay's chip shows; the key is never shown alone. The keys are seven plain
   verbs, the `StatusUpdate.state` values the brain already used plus three: `thinking` (a model
   is generating), `queued` (a subtask waits for room in the subagent budget), `delegating`
   (subtasks run), `swapping` (a handoff holds the card: the pool drains, the deep model loads
   or works, or the cortex comes back, for this turn's handoff or for one it waits behind),
   `folding` (the earlier conversation is being summarized), `calling` (a tool call runs) and
   `asking` (a confirm card waits for the user). `wait` is `""` when the turn waits on none of them. Plain
   verbs, because a chip is read at a glance, like the console's Summon and Dismiss, and each
   word starts with its own letter. Rejected: directions of attention (Inward, Aside, Deeper,
   Outward, Yours), since Aside names a queued and a running subtask alike; and free text with
   no key, which the overlay could neither style nor order.

8. **The key is a string, as `StatusUpdate.state` is.** The same words fill both fields, so an
   enum on one and a string on the other would type one vocabulary twice. The overlay styles only
   `thinking` and shows any other key's sentence as it comes, so a key it does not know degrades
   to a plain chip rather than to a decoding question. The keys are written once, `WAIT_KEYS` in
   `cortex_core/waits.py`.

9. **The brain keeps the wait on the stream's `ProgressSink`.** `ProgressSink.hold(wait)` is an
   async context manager, backed in both implementations by the core's `TurnWaits`, one per
   stream and so one per running turn, never in a model process. Holds nest, and **the innermost
   open wait wins**: `spawn_subagents` is a tool call whose batch waits inside it, a call that needs
   approval asks inside its dispatch, and the deep model's generation runs inside the swap. The holders
   are the tool loop around each model stream (`thinking`), `run_round` around each dispatch that
   was not refused (`calling`), `ToolDispatcher` around the confirmer (`asking`),
   `SummarizingHistoryWindow` around the recap (`folding`), the spawn tool around its batch, and
   `wait_out_handoff` (`cortex_core/handoff_wait.py`) around a wait for another turn's handoff to
   leave the card (`swapping`, through the `ResidencyQueue` port). That last one is announced,
   because the wait can outlast the first gap and the body counts a heartbeat as silence. It is
   taken where the turn would queue: by `TurnEngine` before it reads the history, so the history
   includes what that handoff stores, and by `HandoffAheadBackend` before every model call of a
   stream that can hand off, recall's judge and the recap included. Nothing is awaited between
   that check and the lease, so a scope that begins after the turn starts is still announced.
   A subagent's own loop gets no sink, so its steps never replace the batch's wait. The batch is
   one wait over all its subtasks: `queued` while any has not been admitted, else `delegating`,
   with both counts in the sentence (`2 subtasks running, 1 waiting for room to run`). The runner
   reports admission from inside `SubagentScheduler.admit`, so the scheduler is unchanged.

10. **A change is also sent at once, best effort.** When the innermost wait changes, the record
    sends it as a `StatusUpdate` through the sink, which may drop it; the next heartbeat repeats
    the wait, so a dropped one is set right within a period. A `thinking` wait is never sent as a
    status, because a `thinking` status holds reasoning text that the overlay adds to the
    reply's trace; it reaches the body only in a heartbeat, or as the model's own reasoning. The
    swap conductor already sends its statuses on the turn stream, which does not drop them, so
    `EscalatingTurnEngine` holds each one without sending it again (`announce=False`).

11. **The overlay sets the chip from a heartbeat.** `turnState.ts` sets `status` and
    `statusState` from a heartbeat with a wait, leaves a chip that already shows `thinking` alone
    so the latest reasoning stays on it, ignores an empty wait, and never adds to `thoughts`.

## Consequences

- A brain that stops answering, a path that stops delivering, or a blocked event loop is reported
  within two minutes of the last thing received, instead of up to four hours.
- A turn that stays silent while its brain lives still ends at ADR-0024's bounds.
- A silent turn costs one small message per 30 s, from one task per open stream.
- A return to `thinking` after a tool call reaches the chip with the model's first reasoning, or
  with the next heartbeat for a model that sends none.
- The brain's event loop must not be blocked for more than about 90 s while a turn runs, or the
  body ends the turn. A synchronous call on the loop that long was already a defect, since it
  stalls every stream and the `Health` probe; this makes it visible to the user.

## Alternatives rejected

- **HTTP/2 keepalive** (tonic's `Endpoint::http2_keep_alive_interval` with `keep_alive_timeout`,
  and the `grpc.keepalive_*` options on the brain). An unanswered PING closes the connection, which
  catches a path that stops delivering. But the PING is answered by the HTTP/2 transport in gRPC's
  C core, which runs apart from the Python event loop, so a blocked loop and a stuck turn still
  answer it. A gRPC server also closes a connection whose client pings more often than
  `grpc.http2.min_ping_interval_without_data_ms` allows while no data flows, with a
  `too_many_pings` GOAWAY after `grpc.http2.max_ping_strikes`; gRPC documents those defaults as
  five minutes and two, so a period of minutes needs matching settings on both sides. The heartbeat
  catches everything keepalive would on this stream, since no heartbeat crosses a dead path either.
- **A heartbeat that restarts the idle gap and nothing else.** The gap could then fall to minutes,
  but a turn stuck on a live brain would keep the indicator up until the user pressed Stop.
- **A heartbeat on a timer regardless of the turn.** It would prove only that the stream exists;
  between turns no body is waiting on it.
- **A handoff wait checked only at the turn's start**, even counting a held handoff claim as
  blocking. A scope that begins between that check and the turn's first lease, during its history
  read, recap or recall, still leaves the lease waiting unannounced, so every earlier check only
  narrows that interval.
- **The sink as an argument of `InferenceBackend.stream` and `ModelManager.acquire`.** The same
  effect, but through every implementation of `stream`, most of them test fakes, and the recall
  policy chain the judge sits behind, where one per-stream wrapper needs neither.
- **The sink in a `ContextVar` read at the lease.** It routes a per-stream object through ambient
  state, which [ADR-0022](ADR-0022-email-write-confirmer.md) rejects for the confirmer.
- **The silence or the period inside the message.** The body would then take its own bound from
  the brain it is checking; a constant on each side, compared by `crosscheck`, is simpler.

## Related

- [ADR-0024](ADR-0024-transport-retry.md) (the gaps), [ADR-0010](ADR-0010-subagents.md) (the
  progress sink), [ADR-0047](ADR-0047-delegated-run-bound-ordering.md) (the delegated bounds).
- [body-core-retry.md](../modules/body-core-retry.md),
  [brain-orchestrator.md](../modules/brain-orchestrator.md),
  [body-app.md](../modules/body-app.md), [body-overlay runbook](../runbooks/body-overlay.md).
