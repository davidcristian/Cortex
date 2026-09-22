# A cap that cuts a tool call looks like a dead backend

**Status:** done 2026-08-17
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

Opened 2026-08-16 by the close that passed a finish reason through `InferenceBackend`
([R-206](206-a-finish-reason-the-port-does-not-report.md)), which reports a capped run as `TRUNCATED` everywhere
the run reaches the end of its loop, and left one path where it does not.

A completion cut while the model was still writing a tool call's `arguments` leaves the adapter
with a fragment of JSON, and `finish_calls` raises `InferenceError` on it. The `DecodeStop` has
already been seen by then, since the adapter yields it from the final chunk and assembles the calls
only once the stream is over, so the ledger records that the run was capped. But `PlacedAttempt`
handles an `InferenceError` in its own `except` branch without consulting the ledger, and
`AttemptFailure.INFERENCE` is the one failure the runner retries elsewhere, so this shape cost a
second model load, to be cut at the same cap again.

Reading the ledger in that branch is one line and is not obviously right, which is why the entry
waited. An `InferenceError` can arrive from a round after the capped one: a first completion capped
but whole enough to dispatch its calls, then a dead backend on the second. Reporting that as a
truncation would hide the dead backend and skip the retry that exists for it.

What was built instead is a narrower error type
([ADR-0048](../../adr/ADR-0048-generation-bounds.md)). `finish_calls` now raises
`MalformedToolCallError`, a subclass of `InferenceError` meaning the stream arrived and the
model's own tokens will not parse, and the attempt reports `TRUNCATED` only when that error and a
capped completion are both true. A transport failure on a round after a
capped one raises the wider type and keeps its retry, and an unparsable call under a backend that
reported nothing keeps the previous answer. The one-line fix this entry warned about was run as a
mutation and makes exactly the case the warning names fail.

The shape was reproduced rather than assumed. On a real server, a cap of 20 to 160 tokens on a call
with a long argument streamed 14 to 154 tool-call fragments, closed `finish_reason: "length"`, and
assembled 71 to 899 characters of unterminated JSON; through the shipped adapter and attempt, the
outcome went from `INFERENCE` quoting a JSON decode error to `TRUNCATED` naming the cap.

## History

- 2026-08-16: Opened by the finish-reason close, which left this one path where a capped run does
  not reach the code that reports it.
- 2026-08-17: Done. The narrower error type is what made the ambiguity answerable, and the live
  test that reproduces the cut ships beside it
  (`brain/packages/inference/tests/test_cut_tool_call_live.py`). It opened the same problem one
  layer up, the cortex's own turn, where a cut tool call still fails the turn as an inference error
  ([297](297-cut-tool-call-fails-the-cortex-turn.md)).
