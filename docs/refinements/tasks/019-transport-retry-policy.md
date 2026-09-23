# Transport retry and reconnect policy

**Status:** done 2026-07-08
**Area:** rpc-transport
**Origin:** [ADR-0003](../../adr/ADR-0003-generated-stubs.md)

Backoff and reconnect were added as `RetryingTransport<T, S>`, a decorator in the pure core over
the unchanged `BrainTransport` port, so the `body_rpc` adapter stays thin and its "no retries"
contract is true. It retries the repeatable methods (`health`, `list_sessions`,
`session_messages`) on a transient error (`Connection` or `Rpc{Unavailable}`) with bounded
exponential backoff (`RetryPolicy`), waiting through an injected `Sleeper` port so the schedule is
asserted against a fake with no wall clock. `BrainRpcClient::connect_lazy_with_token` gives it a
reconnecting channel, so a briefly-down brain is retried and tonic reconnects without the caller
noticing; the shell composes it (`seam::connect`, the real `TokioSleeper`, env settings) for the
session-read path. `converse` is forwarded unchanged, being non-idempotent with a one-shot
`decisions` stream, so a failed turn stays terminal.

Jitter and the patient eager dial followed on 2026-07-13
([ADR-0024](../../adr/ADR-0024-transport-retry.md), decisions 4 and 7). A `Randomness` effect
port mirrors `Sleeper`: `FullDelay` is the constant-1 source with no jitter, the real
`ShellRandomness` seeds unit draws from std's `RandomState`, and `CORTEX_BRAIN_RETRY_JITTER=off`
fixes the schedule. It applies equal jitter, `0.5 + 0.5·draw`, keeping half the delay as a floor
so a restarting brain still gets its recovery window, and the draw is sanitized (out of range
clamped, non-finite treated as the full delay) so a bad source cannot panic the `Duration` maths.
The decorator's private loop was extracted as `retry_with(policy, sleeper, randomness, call)` over
any fallible async factory, which `converse.rs` composes around its eager dial; that is safe
because the non-idempotent turn has not begun until the dial succeeds, and a config check in the
lazy constructor keeps a bad URI or token failing fast rather than being retried.
`connect_with_token` stays fail-fast, and the retrying wrapper is composed where it is needed.

Three follow-ups were left behind the same two ports: safe `converse` reconnect before the first
event, a per-method or per-error-code policy, and a retry budget or circuit breaker.

## History

- 2026-07-08: Backoff and reconnect were added as `RetryingTransport<T, S>`, a decorator over the
  unchanged `BrainTransport` port, with a lazy reconnecting constructor for the session-read path
  and `converse` forwarded unchanged so a failed turn stays terminal. It left three follow-ups.
- 2026-07-13: Jitter and the patient eager dial were added: the `Randomness` effect port, equal
  jitter keeping half the delay as a floor, a sanitized draw so a bad source cannot panic the
  `Duration` maths, and `retry_with` composed around `converse.rs`'s eager dial.
- 2026-07-15: Moved out of the ROADMAP's deferred-refinements section into this backlog.
