# Per-method and per-error-code retry policy

**Status:** done 2026-07-16
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

This entry named two things worth very different amounts, and they closed differently.

An audit came first and decided what to build. Every `BrainService` RPC was classified by whether
a repeat can duplicate an effect or change the answer, checked against the brain's own handlers
rather than the method names: the four reads touch no store (`list_due_reminders` maps
`ScheduleStore.deliverable()` and marks nothing delivered), `Converse` runs a turn, `AckReminder`
writes. So nothing non-idempotent was being retried and the defect this entry might have exposed
did not exist. What did not exist was any enforcement: the split was two hand-written `impl`
bodies plus a module comment, so a seventh method added by copying a retried one would have been
retried with nothing reporting it, and this backlog already queued write RPCs for that port.

The per-method half was built. `RpcMethod` names all six port calls and `repeatable()`
classifies each in one exhaustive `match`, so a new variant does not compile until someone decides
about it, and `RetryPlan::policy_for` is the single point every retry decision goes through,
returning `None` for a method that may not be repeated. The decorator runs a `None` on
`RetryPolicy::ONCE`, so `ack_reminder` makes exactly one attempt through the same path rather than
by bypassing it; the first version branched around the loop and left it unreachable, which the
coverage requirement caught. The order of the questions is the substance: repeatability, a fact
about the call, is asked before transience, a fact about the failure, because a status says the
brain could not serve the call and never that the brain did not already run it. The `Health` probe
gained its own ceiling (`RetryPlan::probe_budget`, `CORTEX_BRAIN_PROBE_BUDGET_MS`, default 1 s,
applied as `RetryPolicy::within`, which trims attempts and leaves the delays alone), because the
connection indicator renders that probe's answer. At the shipped defaults the budget does not
bind, the worst case being 600 ms, so behaviour is unchanged; what it removes is the ability to
make the indicator report a stale state by raising `CORTEX_BRAIN_RETRY_ATTEMPTS`.

The per-error-code half was declined for want of a producer: the brain emits exactly `UNAVAILABLE`
(a store or schedule failure), `UNAUTHENTICATED` (the token interceptor), and the `UNIMPLEMENTED`
of a generated default no implemented method reaches. `is_transient` classifies all three
correctly, so a configurable table would have shipped with one live entry. It was reopened as
[R-022](022-retryable-code-table.md).

## History

- 2026-07-08: Recorded as deferred inside the transport retry policy entry, as a per-method or
  per-error-code policy behind the unchanged `BrainTransport` and `Sleeper` ports.
- 2026-07-16: Closed as two different outcomes. The per-method half was built: nothing
  non-idempotent had ever been retried, but the split was enforced only by two hand-written `impl`
  bodies, so it became a single decision point that can answer `None`, and the `Health` probe
  gained a budget. The per-error-code half was declined for want of a producer and reopened as its
  own entry.
- 2026-08-17: The reopened half closed for good as [R-022](022-retryable-code-table.md), declined
  on what the codes mean here rather than on the producer count. Checking that decline again found
  two errors above. The `Health` claim is narrower than written: the probe budget bounds the
  backoff between attempts and not an attempt, so `Down` arrives within `probe_budget` only from a
  brain that answers, and a brain that accepts the connection and then sends nothing still has no
  deadline to hit ([R-301](301-a-per-attempt-deadline-on-the-body-to-brain-calls.md)). And the test enforcing the per-method
  split covered nine of the eleven methods: the `EVERY_METHOD` array called itself every variant
  while omitting `GetPreferences` and `SetPreference`, which is exactly the unreported copy this
  entry was built to prevent, arriving in the test rather than in the `impl`. An exhaustive `match`
  cannot force an array. Both methods are named there now.
