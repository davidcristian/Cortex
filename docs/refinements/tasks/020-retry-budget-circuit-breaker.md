# Retry budget and circuit breaker

**Status:** declined 2026-08-18
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Recorded when the transport retry policy was added, in case a flapping brain ever made blind
retries wasteful. Declined on 2026-08-18 for three reasons.

**Nothing produces the waste it would prevent.** The transient set is exactly `Connection` and
`Rpc{Unavailable}` ([policy.rs](../../../body/crates/core/src/retry/policy.rs)), a `Timeout` is
terminal by decision, and only the five repeatable reads reach the loop at all, every write and
the turn itself running once ([plan.rs](../../../body/crates/core/src/retry/plan.rs)). The
schedule is 3 attempts, 200 ms base, doubling, capped at 2 s, and the probe trims its attempts to
the budget the indicator renders. Nothing polls: the overlay probes on summon and re-checks only
while it is on screen and the link is not ready, one request at a time
([useLink.ts](../../../body/app/src/overlay/useLink.ts)). So the whole population of blind retries
against a flapping brain is at most two extra connect attempts per user action, aimed at a
supervised local process on loopback where a refused connect returns at once.

**The mechanism does not fit the composition.** Breaker state is cross-call, and there is no
cross-call object to hold it: every IPC command builds a fresh transport through `seam::connect()`
and the turn dials its own client, so state inside `RetryingTransport` is discarded with the call
that made it. It would have to live in the shell as process-lifetime shared state, which is a
composition change rather than a decorator change. The open-to-half-open transition also needs to
read a clock, and `Sleeper` can only wait or bound one attempt, so it would need a new effect port
with its own fake and adapter.

**It would introduce the failure the other bounds forbid.** A call refused by stale open state
makes the connection indicator report a state without asking the brain, which is what the probe
budget and the per-attempt deadline exist to prevent.

What was unbounded here was never a flap. It was a brain that accepts the connection and then
sends nothing, which no breaker fixes and which the per-attempt deadline now bounds
([R-301](301-seam-attempt-deadline.md)), an expired deadline being terminal because a retried
deadline is the load amplification a breaker is usually adopted to prevent.

What would reopen this, as a new task: the body growing a background poller, so retries accumulate
while nobody is watching; `CORTEX_BRAIN_ADDR` pointing at a brain that is not a supervised
loopback process; or a blind retry starting to cost seconds rather than microseconds.

## History

- 2026-07-08: Recorded as one of the three follow-ups the transport retry policy left behind.
- 2026-07-16: A retryable-code table beyond `Unavailable` joined it as deferred work, as did safe
  `converse` reconnect before the first event.
- 2026-08-09: A review of those deferred triggers ran against the tree and none had fired.
- 2026-08-18: Declined. The cost claim that it sat behind the same two ports is wrong, because the
  transport is built per call and `Sleeper` cannot read a clock, and the one unbounded cost on
  this interface turned out to be a hang rather than a flap, which the per-attempt deadline now
  bounds.
