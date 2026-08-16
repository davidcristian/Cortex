# A cap that lands mid tool call reads as a dead backend

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first delegated run observed spending a CPU re-run on a task whose GPU attempt was cut at the cap, which the stored detail names as an inference failure while the fragment ends inside a tool call's arguments.

Opened 2026-08-16 by the close that carried a finish reason across `InferenceBackend`
([R-206](206-finish-reason-not-carried.md)), which reports a capped run as `TRUNCATED` everywhere
the run reaches the end of its loop, and leaves one path where it does not.

A completion cut while the model was still writing a tool call's `arguments` leaves the adapter
with a fragment of JSON, and `finish_calls` raises `InferenceError` on it. The `DecodeStop` has
already been observed by then, since the adapter yields it from the final chunk and assembles the
calls only once the stream is over, so the ledger knows the run was capped; but `PlacedAttempt`
answers an `InferenceError` from its own `except` arm without consulting the ledger, and
`AttemptFailure.INFERENCE` is the one failure the runner re-places. So this shape costs a second
model load to be cut at the same cap again.

**Reading the ledger in that arm is one line and is not obviously right, which is why this waits.**
An `InferenceError` can arrive from a round after the capped one: a first completion capped but
whole enough to dispatch its calls, then a dead backend on the second. Reporting that as a
truncation would hide the dead backend and skip the re-place that exists for exactly it. Telling
the two apart needs the ledger to know which completion it was on, or the arm to know whether the
error came from assembling calls or from the transport, and neither exists today. The failure this
would fix is also rare by construction: a tool call's arguments are short and the shipped cap is
1024 decoded tokens, so the cut has to land inside the last few tokens of a round.
