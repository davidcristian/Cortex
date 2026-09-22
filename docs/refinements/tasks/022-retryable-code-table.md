# A retryable-code table beyond `Unavailable`

**Status:** declined 2026-08-17
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Declined on its merits rather than deferred a third time. Reading the code again found the same
two statuses this server has always written, `UNAVAILABLE` from a store, schedule, memory or
preference failure and `UNAUTHENTICATED` from the token interceptor, plus the `UNIMPLEMENTED` of a
generated default no implemented method reaches. What changed is the reasoning rather than the
count: waiting for a producer treated the three candidate codes as correct but unproduced, and
read against this interface each of them is wrong here. `RESOURCE_EXHAUSTED` is the clearest case,
because the one producer anywhere in this repo raises it for a screen capture too large to send,
which is a payload a repeat resends unchanged, so treating the code as retryable would be exactly
backwards. `ABORTED` is a store-contention convention no handler follows, and `DEADLINE_EXCEEDED`
cannot arrive while nothing here sets a deadline.

The idempotency question this entry existed to raise is answered by the structure. A code table is
dangerous when a status judged transient reaches a call that must not repeat, and that cannot
happen: `RetryPlan::policy_for` rejects an unrepeatable method before any error exists, so no
classification this table could hold reaches `Converse`, `AckReminder` or a catalog write. The
table is therefore a pure question about the failure, and widening it later is a one-line change
that cannot become a correctness bug, which is the strongest reason not to build configuration for
it now.

## History

- 2026-07-16: Opened when the per-error-code half of the per-method policy was declined for want
  of a producer. The brain emits exactly `UNAVAILABLE`, `UNAUTHENTICATED` and the `UNIMPLEMENTED`
  of a generated default, all three already classified correctly.
- 2026-08-09: A review found this trigger looks fired and is not. The `RESOURCE_EXHAUSTED`
  classification added on 2026-08-08 is raised by the body's service for `CaptureError::TooLarge`
  (`body/crates/rpc/src/screen.rs:124`) and consumed by the brain as a client, which maps it to
  `BodyFailure.OVERSIZE`
  (`brain/packages/body_client/src/cortex_body_client/failures.py:40`), while the retry policy
  this entry is about classifies the body-to-brain direction at
  `body/crates/core/src/retry/policy.rs:26`, whose transient set is still exactly `Unavailable`.
  Every brain-side abort is still `UNAVAILABLE` or `UNAUTHENTICATED`.
- 2026-08-17: Declined. Reading the three candidate codes against this interface rather than
  against gRPC convention found each of them wrong here rather than merely unproduced. The
  classification is now argued per code at the origin and asserted by a test that fails when the
  set grows, so a widening is deliberate. Two smaller findings came out of the same reading: the
  idempotency hazard cannot arise, because repeatability is asked before transience, and the
  test enforcing the whole-port rule covered nine of eleven methods, `EVERY_METHOD` omitting
  `GetPreferences` and `SetPreference`. The residue is [R-301](301-a-per-attempt-deadline-on-the-body-to-brain-calls.md): the
  probe budget bounds backoff and not the calls, so a brain that accepts a connection and never
  answers has no deadline to hit.
