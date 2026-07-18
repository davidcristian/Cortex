# Seam transport & retry

The deferrals here originate at [ADR-0003](../adr/ADR-0003-seam-codegen.md), which defined the seam codegen and left transport hardening for later, and were largely resolved by [ADR-0024](../adr/ADR-0024-transport-retry.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** safe `converse` reconnect-before-first-event, retry budget / circuit-breaker, a retryable-code table beyond `Unavailable`, a disconnect mid handoff blocking the stream's teardown

**Seam / transport in Slice 2 ([ADR-0003](../adr/ADR-0003-seam-codegen.md)):**
- **Transport retry / reconnect policy landed 2026-07-08 ([ADR-0024](../adr/ADR-0024-transport-retry.md)).**
  The deferred backoff/reconnect refinement, added as a **decorator over the unchanged
  `BrainTransport` port** so the `body_rpc` adapter stays thin (its "no retries" contract is now
  true by construction): `RetryingTransport<T, S>` (pure core) retries the **idempotent** methods
  (`health`, `list_sessions`, `session_messages`) on a transient error (`Connection` /
  `Rpc{Unavailable}`) with bounded exponential backoff (`RetryPolicy`), waiting via an injected
  `Sleeper` port so the schedule is asserted with a fake (no wall-clock, 100%-gated). A new lazy
  constructor (`BrainSeamClient::connect_lazy_with_token`) gives it a reconnecting channel, so a
  briefly-down brain is retried and tonic reconnects transparently; the ungated shell composes it
  (`seam::connect`, real `TokioSleeper`, env knobs) for the session-read path. `converse` is
  forwarded **unchanged** (non-idempotent, one-shot `decisions` stream), so a failed turn stays
  terminal. **Jitter and the patient eager dial landed 2026-07-13
  ([ADR-0024 addendum](../adr/ADR-0024-transport-retry.md)):** a `Randomness` effect port (mirroring
  `Sleeper`; `FullDelay` is the constant-1 no-jitter source, real `ShellRandomness` seeds unit
  draws from std's `RandomState`, `CORTEX_BRAIN_RETRY_JITTER=off` pins the schedule) applies
  **equal jitter** (`0.5 + 0.5·draw`, half kept as a floor so a restarting brain still gets its
  recovery window), the draw sanitized (out-of-range clamped, non-finite treated as the full
  delay) so a bad source cannot panic the `Duration` math; and the
  decorator's private loop is extracted as `retry_with(policy, sleeper, randomness, call)` over any
  fallible async factory, which `converse.rs` composes around its **eager** dial (safe because the
  non-idempotent turn has not begun until the dial succeeds; the terminal-turn contract is
  untouched, and a lazy-constructor config gate keeps a bad URI or token fail-fast rather than
  retried). `connect_with_token` stays fail-fast; patience is composed where wanted. Remaining
  behind the same `BrainTransport`/`Sleeper` seams (ADR-0024 deferred):
  **safe `converse` reconnect-before-first-event** (needs a replayable request + a signature
  change); a **per-method / per-error-code policy**; and a **retry budget /
  circuit-breaker** if a flapping brain ever makes blind retries wasteful.
- **Per-method policy landed 2026-07-16; the per-error-code half declined
  ([ADR-0024 addendum](../adr/ADR-0024-transport-retry.md)).** The entry named two things and
  they were worth very different amounts, which is the third entry in two days to prove that an
  item naming two things should be read as two. Its "behind the existing
  `BrainTransport`/`Sleeper` seams" claim held: both ports are untouched, as is `Randomness`.
  **The audit first, since it decided what to build.** Every `BrainService` RPC was classified
  by whether a repeat can duplicate an effect or change the answer, checked against the brain's
  own handlers rather than the method names: the four reads touch no store (`list_due_reminders`
  maps `ScheduleStore.deliverable()` and marks nothing delivered), `Converse` runs a turn,
  `AckReminder` writes. So **nothing non-idempotent was being retried** and the defect this
  entry could have exposed does not exist. What did not exist was any *enforcement*: the split
  was two hand-written `impl` bodies plus a module comment, and a seventh method added by
  copying a retried one would have been retried in silence. This backlog already queues write
  RPCs for that very port (session deletion / rename / pinning), so the copy was coming.
  **What landed** is the classification made structural and the schedule made per method:
  `SeamMethod` names all six port calls and `repeatable()` classifies each in one exhaustive
  `match` (a new variant does not compile until someone decides), and `RetryPlan::policy_for`
  is the single door every retry decision goes through, returning `None` for a method that may
  not be repeated at all. The decorator runs a `None` on `RetryPolicy::ONCE`, so `ack_reminder`
  makes exactly one attempt *by the gate* rather than by bypassing the retry path, and a
  refusal takes no route a permitted call does not (the first shape branched around the loop
  and left it monomorphized-but-unreachable, which the coverage gate caught). The
  question order is the substance: repeatability (a fact about the call) is asked before
  transience (a fact about the failure), because a status says the brain could not serve the
  call and never that the brain did not already run it. The `Health` probe then gets its own
  ceiling (`RetryPlan::probe_budget`, `CORTEX_BRAIN_PROBE_BUDGET_MS`, default 1 s, applied as
  `RetryPolicy::within`, which trims attempts and leaves the delays alone): the connection
  indicator renders that probe's answer, so patience past the budget is the dot claiming a
  state the seam stopped proving. At the shipped defaults the budget does not bind (600 ms
  worst case), so behaviour is unchanged out of the box; what it removes is the ability to make
  the indicator lie by raising the reads' `CORTEX_BRAIN_RETRY_ATTEMPTS`.
  **The per-error-code half is declined for want of a producer**, the same test that closed the
  blended-relevance and `GetVolume` entries: the brain emits exactly `UNAVAILABLE` (a store or
  schedule failure), `UNAUTHENTICATED` (the seam-token interceptor), and the `UNIMPLEMENTED` of
  a generated default no implemented method reaches. `is_transient` classifies all three
  correctly today, so a configurable retryable-code table would ship with one live entry. It
  moves to fix-when-it-bites below with its trigger named.
- **A retryable-code table beyond `Unavailable`** (fix when it bites, opened 2026-07-16 by the
  entry above). Its trigger is a producer: a brain that answers `RESOURCE_EXHAUSTED` (an
  admission or GPU-lease wall surfacing on the seam rather than inside a turn) or `ABORTED` (a
  store contention retry). Both are conventionally retryable and both are ambiguous about
  whether the server already did the work, so each would need the repeatability gate consulted
  first exactly as `Unavailable` now is. Until one exists, widening the set widens only the
  configuration surface. `DEADLINE_EXCEEDED` is not on that list and is a separate question:
  nothing on this seam sets a deadline.
- **Safe `converse` reconnect-before-first-event: sharpened and moved to fix-when-it-bites
  2026-07-16 ([ADR-0024 addendum](../adr/ADR-0024-transport-retry.md)).** Its one-line cost ("a
  replayable request and a signature change") was right about the shape and silent about the size.
  Read against both sides of the seam: a `converse` turn's first durable effect is
  `await self._store.append(session_id, user)` in `TurnEngine.handle_turn` (`engine.py`), run
  before inference and before the first yielded event, on an independent turn task that advances
  whether or not the client reads (`converse_stream.py`, a `UserTurn` starts `_turn_task` and its
  events land on a queue the consumer drains separately). So "the client saw no event" never means "the
  brain did nothing": by then the user message is stored and a tool the model asked for first may
  have run. And nothing carries request identity: `ClientEvent` and `UserTurn` hold `session_id`,
  text, and images, no request id or idempotency key, and the `turn_id` is minted server-side, so a
  reconnect that re-issues the request double-runs the turn (verified live over the real engine, an
  identical resend leaves two user messages under two distinct turn ids). A provably-safe version
  needs a client-generated request id (a proto field, both stubs regenerated) or a resumable cursor,
  plus a Redis-backed idempotency/resume registry keyed by `(session_id, request_id)` that survives
  a model swap (the one hard rule) and either replays a completed turn's outcome or re-attaches to
  an in-flight turn's buffered events. That is a turn-lifecycle state machine, an idempotency store,
  and an event-replay path, and it reverses the deliberate "an in-flight turn is disposable, its
  partial reply dropped" design. Disproportionate at personal loopback scale where reconnects are
  rare and a dropped turn is already terminal (the user resends), so it waits for a trigger: routine
  mid-turn evictions once the real model swap lands, and turns costly enough that a silent re-run
  beats paying for dedup. `converse` stays unretried (`SeamMethod::Converse` is not repeatable);
  this sharpen is why, not a change to it.
- **A disconnect mid handoff blocks the stream's teardown until the cortex is back.** *Fix when
  it bites.* Opened 2026-07-17 by the brain-handoff conductor sub-slice
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 5). The swap back is the recovery path,
  so `swap_scope`'s restore now runs as its own shielded task and **every** cancellation waits for
  it before propagating: without that, a client that disconnected while the cortex was coming back
  left the process with no resident model and every later turn failing (found by the chaos suite,
  and fixed there). Every one and not just the first, because this stream delivers two whenever a
  client `Cancel` is followed by the stream's own teardown (`_cancel_turn` from the pump, then
  again from `events()`'s `finally`), and a single shielded wait is abandoned by the second, which
  put the drain window back up while the GPU was still empty. The cost is on the other side: the
  Converse stream's `_cancel_turn` awaits the
  turn task, so a `Cancel` or a disconnect during a handoff holds the RPC's teardown for as long as the
  restore takes, which is seconds against the scripted host and minutes against real weights. The
  alternative is to detach the restore (fire it, return, and let boot recovery be the backstop),
  which trades a bounded wait for a window where the process believes nothing is resident while a
  restore it no longer tracks is still running. The trigger is a real deployment where a
  disconnect during a swap holds a teardown long enough to matter; the fix belongs with the
  in-flight-turn lifecycle above, not on its own.
