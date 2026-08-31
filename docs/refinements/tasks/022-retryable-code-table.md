# A retryable-code table beyond `Unavailable`

**Status:** declined 2026-08-17
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Declined on its merits rather than deferred a third time. The producer sweep re-ran against the
code and found the same two statuses this seam's server has always written, `UNAVAILABLE` from a
store, schedule, memory or preference failure and `UNAUTHENTICATED` from the seam-token
interceptor, plus the `UNIMPLEMENTED` of a generated default no implemented method reaches. What
changed is the reasoning rather than the count: waiting for a producer treated the three candidate codes
as correct-but-unproduced, and read against this seam each is instead *wrong* here.
`RESOURCE_EXHAUSTED` is the sharpest, because the one producer anywhere in this repo raises it for
a screen capture too large to send, which is a payload a repeat resends unchanged, so the
conventionally retryable reading of the code would be exactly inverted. `ABORTED` is a
store-contention convention no handler performs, and `DEADLINE_EXCEEDED` cannot arrive while
nothing on this seam sets a deadline.

The idempotency question this entry existed to raise turns out to be structurally answered.
A code table is dangerous when a status judged transient reaches a call that must not repeat, and
that cannot happen here: `RetryPlan::policy_for` rejects an unrepeatable method before any error
exists, so no classification this table could ever carry reaches `Converse`, `AckReminder`, or a
catalog write. The table is therefore a pure question about the failure, and widening it later is
a one-line change that cannot become a correctness bug, which is the strongest reason not to build
configuration for it now.

## Trail

- 2026-07-16: opened by the per-method and per-error-code entry when the per-error-code half was
  declined for want of a producer. The brain emits exactly `UNAVAILABLE`, `UNAUTHENTICATED` and the
  `UNIMPLEMENTED` of a generated default, all three already classified correctly, so a configurable
  table would have shipped with one live entry. It joined the retry budget and circuit-breaker in
  the fix-when-it-bites bucket.
- 2026-08-09: the trigger sweep of that bucket found this trigger looks fired and is not, which was
  the sharpest of its findings. The `RESOURCE_EXHAUSTED` classification that landed 2026-08-08 is
  raised by the body's service for `CaptureError::TooLarge` (`body/crates/rpc/src/screen.rs:124`)
  and consumed by the brain as a client, which maps it to `BodyFailure.OVERSIZE`
  (`brain/packages/body_client/src/cortex_body_client/failures.py:40`), while the retry policy this
  entry is about classifies the body-to-brain direction at
  `body/crates/core/src/retry/policy.rs:26`, whose transient set is still exactly `Unavailable`, and
  every brain-side abort is still `UNAVAILABLE` or `UNAUTHENTICATED`
  (`session_servicer.py:64,76,88,99,110`, `preference_servicer.py:46,62`, `server.py:201,212`,
  `auth.py:44,52`). The trigger names a producer on the seam the policy reads, and what landed is
  a producer on the other one.
- 2026-08-17: declined, and the deferral's own premise is what decided it. Re-deriving the sweep
  confirmed both halves of the 2026-08-09 finding unchanged, and then reading the three candidate
  codes against *this* seam rather than against gRPC convention found each of them wrong here
  rather than merely unproduced, which is a decline and not another wait. The classification is
  now argued per code in the origin decision and pinned by a test that fails when the set grows,
  so a widening is deliberate. Two smaller things came out of the same reading. The idempotency
  hazard the entry was really about cannot arise, because repeatability is asked before
  transience, which is also what makes a future one-code widening cheap. And the gate's whole-port
  invariant was covering nine of eleven methods: `EVERY_METHOD` called itself every variant while
  omitting `GetPreferences` and `SetPreference`, which the exhaustive `match` in `repeatable()`
  cannot force, so both are named now and in the explicit assertions beside it. The residue is
  [301](301-seam-attempt-deadline.md): the probe budget bounds backoff and not the calls, so a
  brain that accepts a connection and never answers has no deadline to hit.
