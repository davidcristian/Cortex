# A retryable-code table beyond `Unavailable`

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** a producer, meaning a brain that answers `RESOURCE_EXHAUSTED` or `ABORTED`.

Its trigger is a producer: a brain that answers `RESOURCE_EXHAUSTED` (an
admission or GPU-lease wall surfacing on the seam rather than inside a turn) or `ABORTED` (a
store contention retry). Both are conventionally retryable and both are ambiguous about
whether the server already did the work, so each would need the repeatability gate consulted
first exactly as `Unavailable` now is. Until one exists, widening the set widens only the
configuration surface. `DEADLINE_EXCEEDED` is not on that list and is a separate question:
nothing on this seam sets a deadline.

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
  `auth.py:44,52`). The trigger wants a producer on the seam the policy reads and what landed is a
  producer on the other one.
