# Per-method and per-error-code retry policy

**Status:** landed 2026-07-16
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

The entry named two things and
they were worth very different amounts, which is the third entry in two days to prove that an
item naming two things should be read as two. Its "behind the existing
`BrainTransport`/`Sleeper` seams" claim held: both ports are untouched, as is `Randomness`.
**The audit first, since it decided what to build.** Every `BrainService` RPC was classified
by whether a repeat can duplicate an effect or change the answer, checked against the brain's
own handlers rather than the method names: the four reads touch no store (`list_due_reminders`
maps `ScheduleStore.deliverable()` and marks nothing delivered), `Converse` runs a turn,
`AckReminder` writes. So **nothing non-idempotent was being retried** and the defect this
entry could have exposed does not exist. What did not exist was any *enforcement*: the split
was two hand-written `impl` bodies plus a module comment, and a seventh method added by
copying a retried one would have been retried in silence. This backlog already queues write
RPCs for that very port (session deletion / rename / pinning), so the copy was coming.
**What landed** is the classification made structural and the schedule made per method:
`SeamMethod` names all six port calls and `repeatable()` classifies each in one exhaustive
`match` (a new variant does not compile until someone decides), and `RetryPlan::policy_for`
is the single door every retry decision goes through, returning `None` for a method that may
not be repeated at all. The decorator runs a `None` on `RetryPolicy::ONCE`, so `ack_reminder`
makes exactly one attempt *by the gate* rather than by bypassing the retry path, and a
refusal takes no route a permitted call does not (the first shape branched around the loop
and left it monomorphized-but-unreachable, which the coverage gate caught). The
question order is the substance: repeatability (a fact about the call) is asked before
transience (a fact about the failure), because a status says the brain could not serve the
call and never that the brain did not already run it. The `Health` probe then gets its own
ceiling (`RetryPlan::probe_budget`, `CORTEX_BRAIN_PROBE_BUDGET_MS`, default 1 s, applied as
`RetryPolicy::within`, which trims attempts and leaves the delays alone): the connection
indicator renders that probe's answer, so patience past the budget is the dot claiming a
state the seam stopped proving. At the shipped defaults the budget does not bind (600 ms
worst case), so behaviour is unchanged out of the box; what it removes is the ability to make
the indicator lie by raising the reads' `CORTEX_BRAIN_RETRY_ATTEMPTS`.
**The per-error-code half is declined for want of a producer**, the same test that closed the
blended-relevance and `GetVolume` entries: the brain emits exactly `UNAVAILABLE` (a store or
schedule failure), `UNAUTHENTICATED` (the seam-token interceptor), and the `UNIMPLEMENTED` of
a generated default no implemented method reaches. `is_transient` classifies all three
correctly today, so a configurable retryable-code table would ship with one live entry. It
moves to fix-when-it-bites below with its trigger named.

## Trail

- 2026-07-08: recorded as deferred inside the transport retry and reconnect policy entry, as a
  per-method or per-error-code policy behind the unchanged `BrainTransport` and `Sleeper` seams.
- 2026-07-16: closed as two different outcomes, the third area in two days to show that an entry
  naming two things is two entries, and the rare one whose "behind the existing seams" claim held
  exactly. The per-method half landed: the audit it began with found that nothing non-idempotent was
  ever retried, so the defect it might have exposed does not exist, but the split was enforced only
  by two hand-written `impl` bodies while this backlog already queues write RPCs for that port, so
  the silent copy was coming. The gate is now a single door that can answer `None`, and the `Health`
  probe got a budget, so raising the reads' retry knobs can no longer slow what the connection
  indicator claims. The per-error-code half was declined for want of a producer, the same test that
  closed blended relevance and `GetVolume`, and reopened as a retryable-code table with its trigger
  named, so the area count held at 3.
