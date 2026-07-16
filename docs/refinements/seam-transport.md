# Seam transport & retry

The deferrals here originate at [ADR-0003](../adr/ADR-0003-seam-codegen.md), which defined the seam codegen and left transport hardening for later, and were largely resolved by [ADR-0024](../adr/ADR-0024-transport-retry.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** safe `converse` reconnect-before-first-event, per-method / per-error-code policy, retry budget / circuit-breaker

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
