# Retry budget and circuit breaker

**Status:** declined 2026-08-18
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

A **retry budget / circuit-breaker** if a flapping brain ever made blind retries wasteful,
recorded as remaining "behind the same `BrainTransport`/`Sleeper` seams" when the transport retry
and reconnect policy landed. Declined on its merits rather than deferred a fourth time, and the
re-derivation that decided it found that phrase to be false as written, which is the shape the
backlog's standing warning describes.

**There is no producer for the waste this exists to prevent.** Read against the tree on
2026-08-18: the transient set is exactly `Connection` and `Rpc{Unavailable}`
([policy.rs](../../../body/crates/core/src/retry/policy.rs)), a `Timeout` is terminal by decision,
and only the five repeatable reads reach the loop at all, every write and the turn itself running
once ([plan.rs](../../../body/crates/core/src/retry/plan.rs)). The shipped schedule is 3 attempts,
200 ms base, doubling, capped at 2 s, and the probe trims its attempts to the budget the indicator
renders. Nothing polls: the overlay probes on summon and re-checks only while it is on screen and
the link is not ready, single-flighted, with a liveness poll rejected in that file's own header
([useLink.ts](../../../body/app/src/overlay/useLink.ts)). So the entire population of blind retries
against a flapping brain is at most two extra connect attempts per user action, aimed at a
supervised local process on loopback, where a refused connect returns at once. A breaker sheds
load for a shared or remote peer with many clients; here it would save microseconds nobody spends.

**And the mechanism does not fit the composition it would have to fit.** Breaker state is cross-call
by definition, and there is no cross-call object to hold it: every IPC command builds a fresh
transport through `seam::connect()` (the session reads, the reminder calls, the link probe, the
preference calls), and the turn dials its own client, so state inside `RetryingTransport` is discarded
with the call that made it. It would have to live in the shell as process-lifetime shared state,
which is a composition change rather than a decorator change. The open-to-half-open transition
then needs to read a clock, and `Sleeper` can only wait or bound one attempt, never say what time
it is, so it needs a new effect port with its own fake and adapter. That is two seam changes rather than none.

**A breaker would also introduce the failure the seam's other bounds were built to forbid.** A
call refused by stale open state makes the connection indicator report a state without asking the
brain, which is exactly what the probe budget and the per-attempt deadline exist to prevent.

**What was actually unbounded here was never a flap.** It was a brain that accepts the connection
and then sends nothing, which no breaker fixes and which the per-attempt deadline now bounds
([301](301-seam-attempt-deadline.md)), with an expired deadline terminal because a retried
deadline is the load amplification a breaker is usually adopted to prevent.

**What would reopen this**, as a new task rather than a resumption of this one: the body growing a
background poller, so retries accumulate while nobody is watching; `CORTEX_BRAIN_ADDR` pointing at
a brain that is not a supervised loopback process, meaning a shared or remote one with other
clients; or a blind retry starting to cost seconds rather than microseconds, which is what a
non-local peer or a queueing brain would make of it.

## Trail

- 2026-07-08: recorded as one of the three refinements the transport retry and reconnect policy
  entry named as remaining when it landed.
- 2026-07-16: a retryable-code table beyond `Unavailable` joined it in the fix-when-it-bites bucket,
  and safe `converse` reconnect-before-first-event joined it there the same day.
- 2026-08-09: a trigger sweep of that whole bucket ran against the tree and fired nothing, recorded
  in the index so the next reader spends the pass elsewhere instead of re-deriving the verdicts.
- 2026-08-18: declined, on a re-derivation rather than on the sweep's verdict. The producer picture
  above is what the code says today, the "behind the same seams" cost claim is refuted by the
  per-call transport and by `Sleeper` having no clock read, and the one unbounded cost on this seam
  turned out to be a hang rather than a flap, which the per-attempt deadline now in the tree
  bounds.
  The reasoning is recorded at the origin decision as well.
