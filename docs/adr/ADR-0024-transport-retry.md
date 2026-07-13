# ADR-0024: Transport retry / reconnect decorator (Slice 2 refinement)

- **Status:** Accepted
- **Date:** 2026-07-08

## Context

Slice 2 shipped the body's `BrainSeamClient` (the tonic adapter behind the
`body_core::BrainTransport` port) as **thin translation with no retries**. A dropped
stream or a transient reachability failure surfaces straight to the caller, and the overlay
treats a failed turn as terminal. That refinement was deferred at
[ADR-0003](ADR-0003-seam-codegen.md) (addendum) and recorded in the ROADMAP ledger. This ADR
lands it.

The concrete failure the refinement targets: the brain is *briefly* unavailable, because it is
restarting after a model swap, or a momentary loopback blip drops the connection, and a
read the overlay makes (`list_sessions` for the switcher) fails hard when a retry a beat
later would have succeeded. The brain is a supervised local process that comes back within
seconds; a single automatic retry with backoff turns a user-visible error into a hidden
hiccup.

Constraints from AGENTS.md the design must respect:

- **The adapter stays thin.** Retry *policy* is business logic; per the hexagonal rule an
  adapter holds none. So retry cannot live inside `BrainSeamClient`.
- **The core is pure, with no I/O and no OS APIs.** A backoff sleep is a timer effect (an OS
  clock). It cannot be called from `body_core` directly; it must be an injected port.
- **100% line+branch coverage without a network or a wall-clock.** Whatever holds the retry
  loop must be testable deterministically, with no real timers and no real sockets.

## Decisions

1. **Retry is a decorator over the port, not code in the adapter.**
   `RetryingTransport<T: BrainTransport, S: Sleeper>` (in `body_core::retry`) *is* a
   `BrainTransport`: it wraps an inner transport `T` and adds a bounded-retry loop around the
   inner calls. Generic over any `BrainTransport`, so it is exercised in full against a fake
   inner transport with zero network. The real `BrainSeamClient` stays byte-for-byte the thin
   translation it was. Its "no retries" contract is now *true by construction*, with
   resilience composed on top.

2. **Only the idempotent methods are retried.** `health`, `list_sessions`, and
   `session_messages` are read-only (repeating one has no side effect), so they retry on a
   transient failure. **`converse` is pass-through, unchanged.** It is non-idempotent (a turn
   may run tools, stream partial output, mutate session state), its `decisions` argument is a
   one-shot `impl Stream + 'static` that cannot be replayed across attempts, and the overlay's
   contract already treats a failed turn as terminal. The decorator forwards `converse`
   straight to the inner transport and never retries it. (Safe reconnect of `converse` *before
   the first event* is a distinct, harder change. It needs a replayable request and a
   different signature. It stays deferred.)

3. **Transient = `Connection` or `Rpc{Unavailable}`; everything else is terminal.**
   `is_transient` (pure) classifies a `TransportError`:
   - `Connection(_)` → retry. An unreachable brain, or a transport failure before a reply, is
     the clearest "try again" signal (a lazy channel surfaces a down endpoint here).
   - `Rpc { code, .. }` → retry **iff** `code == "Unavailable"`, the gRPC convention for a
     transient backend condition (the session reads already surface a store-down abort as
     `Unavailable`). Every other status (`Internal`, `Unimplemented`, `Unauthenticated`, …) is
     a genuine application answer (a repeat would return the same thing), so it is terminal.
   - `Protocol(_)` → terminal. Malformed wire data will not reinterpret on a repeat.

4. **Bounded exponential backoff, no jitter (v1).** `RetryPolicy` (pure, `Copy`): `max_attempts`
   (total tries incl. the first; `1` disables retry), `base_delay`, `multiplier`, `max_delay`
   (the cap). The delay before retry *k* (0-based) is `min(base_delay · multiplierᵏ, max_delay)`,
   computed by saturating multiply so no overflow escapes the cap. Jitter is omitted from v1:
   it needs a randomness effect (a second injected port), and with a single supervised local
   peer the thundering-herd problem jitter solves does not arise. Recorded as deferred.

5. **A `Sleeper` port makes time an injected effect.** `Sleeper::sleep(&self, Duration) ->
   impl Future + Send` is the one seam the decorator uses to wait between attempts. Tests inject
   a `FakeSleeper` that records the requested durations and returns immediately, so the backoff
   *schedule* is asserted deterministically with no real time elapsing. The real adapter,
   `TokioSleeper` (a one-line `tokio::time::sleep`), lives in the ungated Tauri shell (the
   composition root, host-validated), keeping the timer effect out of the gated crates.

6. **A lazy channel makes the decorator load-bearing for the dial too.** The existing eager
   `BrainSeamClient::connect[_with_token]` fails immediately when the brain is down, so the
   decorator would never get a turn. So `body_rpc` gains
   `connect_lazy_with_token`, which builds the client over tonic's `Channel::connect_lazy`:
   construction only fails on a bad URI or bad token, never on reachability, and each RPC
   (re)establishes the connection on demand. Composed under `RetryingTransport`, a call against a
   briefly-down brain now fails `Connection`, the decorator waits and retries, and tonic
   transparently reconnects when the brain returns. Eager `connect` stays for callers that want
   fail-fast (the live tests, a future health probe that should report "down" rather than block).

7. **Wired for the read path; `converse` unchanged.** The shell composes
   `RetryingTransport::new(connect_lazy_with_token(...), TokioSleeper, RetryPolicy::from_env)` in
   the shared `connect()` used by `list_sessions` / `session_messages`. The policy is
   configurable via env (`CORTEX_BRAIN_RETRY_ATTEMPTS`, `_BASE_MS`, `_MULTIPLIER`, `_MAX_MS`),
   defaulting to 3 attempts / 200 ms base / ×2 / 2 s cap. `converse.rs` keeps its eager dial and
   terminal-turn behavior, which matches decision 2.

## Consequences

- A genuinely-down brain now costs the read path up to `(max_attempts − 1)` backoff waits
  before it surfaces the error (bounded: ≤ 2 × 2 s with the defaults). A deliberate trade of a
  little latency-on-failure for resilience-to-blips; the overlay's `.catch` still renders the
  final error if every attempt fails.
- A brain that (mis)reports `Unavailable` for a non-transient condition will be retried. That
  is the documented gRPC contract for the code, so treating it as transient is correct; a brain
  that wants "do not retry" uses any other status.
- The `Sleeper` port is a new, reusable seam. Any later body-side backoff (reconnect loops,
  poll intervals) injects the same effect and tests against the same fake.
- `converse` resilience is explicitly *not* delivered: a dropped turn stays terminal. The
  overlay's existing "failed turn is terminal" contract is unchanged, so nothing regresses.

**Deferred (behind the unchanged `BrainTransport` / `Sleeper` seams), recorded in the ROADMAP
ledger:** randomized jitter; safe `converse` reconnect-before-first-event (replayable request +
signature change); dial-retry for the *eager* `connect` (the lazy path covers the shell); a
per-method or per-error-code policy; and a retry budget / circuit-breaker if a flapping brain
ever makes blind retries wasteful.

## Addendum (2026-07-13): jitter and the patient eager dial land

Two of the deferrals land together, behind the unchanged `BrainTransport`/`Sleeper` seams.

**Equal jitter over a `Randomness` port.** The randomness effect decision 4 called for:
`Randomness::unit(&self) -> f64` (a value in `[0, 1]`), mirroring `Sleeper` exactly (real
adapter in the ungated shell, deterministic fake in tests). The retry loop scales each
computed delay by `0.5 + 0.5 * unit()` (equal jitter): half the delay stays as a floor,
because this wait's purpose is giving a restarting local brain time to come back, not only
decorrelating a herd, and a zero-floor draw would burn an attempt instantly. The drawn
value is sanitized first (out-of-range clamped into `[0, 1]`, a non-finite draw treated as
the full delay, since `clamp` would otherwise pass a `NaN` through to a panicking
`mul_f64`), so a misbehaving source degrades the spread rather than crashing the loop.
`FullDelay`, the constant-1 source, degenerates the formula to the exact v1
schedule; `RetryingTransport::new` uses it, so existing compositions and the schedule
tests hold unchanged, and `with_randomness` opts a composition in. The shell adapter
(`ShellRandomness`) draws its unit values from `std::collections::hash_map::RandomState`
(std's per-instance random seed), which is jitter-grade spread without a new dependency;
`CORTEX_BRAIN_RETRY_JITTER=off` pins it to 1, restoring the deterministic schedule, and
the default is on.

**The patient eager dial.** The decorator's private retry loop is extracted as a public
`retry_with(policy, sleeper, randomness, call)` helper over any fallible async factory
(the transport's idempotent methods now delegate to it). `converse.rs` composes it around
its eager `connect_with_token`, so a turn started against a briefly-down brain retries the
dial instead of failing on the first refused connect. This is safe precisely because the
non-idempotent turn has not begun until the dial succeeds, so it does not touch decision
2's terminal-turn contract. A permanent misconfiguration (bad URI, non-ASCII token) would
otherwise be retried for the whole budget, since it surfaces as the same `Connection`
error a down brain does, so `converse` first runs the lazy constructor as a synchronous
config gate (it validates URI and token without dialing, the same fast-fail the read path
already gets) and only the reachability dial is retried. `connect_with_token` itself stays
fail-fast (decision 6's callers are unchanged); patience is composed where it is wanted,
never baked in.

Still deferred (ROADMAP ledger): safe `converse` reconnect-before-first-event, the
per-method / per-error-code policy, and the retry budget / circuit breaker.
