# Retry budget and circuit breaker

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** a flapping brain that makes blind retries wasteful.

A **retry budget / circuit-breaker** if a flapping brain ever makes blind retries wasteful,
remaining behind the same `BrainTransport`/`Sleeper` seams (ADR-0024 deferred).

This item had no entry of its own, having been recorded as a clause inside the transport retry and
reconnect policy entry, in that entry's list of what stayed deferred when it landed.

## Trail

- 2026-07-08: recorded as one of the three refinements the transport retry and reconnect policy
  entry named as remaining when it landed.
- 2026-07-16: a retryable-code table beyond `Unavailable` joined it in the fix-when-it-bites bucket,
  and safe `converse` reconnect-before-first-event joined it there the same day.
- 2026-08-09: a trigger sweep of that whole bucket ran against the tree and fired nothing, recorded
  in the index so the next reader spends the pass elsewhere instead of re-deriving the verdicts.
