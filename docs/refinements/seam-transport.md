# Seam transport & retry

The deferrals here originate at [ADR-0003](../adr/ADR-0003-seam-codegen.md), which defined the seam codegen and left transport hardening for later, and were largely resolved by [ADR-0024](../adr/ADR-0024-transport-retry.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** safe `converse` reconnect-before-first-event, retry budget / circuit-breaker, a retryable-code table beyond `Unavailable`

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
