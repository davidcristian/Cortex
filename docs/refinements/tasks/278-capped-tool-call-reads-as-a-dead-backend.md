# A cap that lands mid tool call reads as a dead backend

**Status:** landed 2026-08-17
**Area:** subagents
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

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

**What landed is the second of those two, which turned out to be the cheap one**
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) tool-call-cut addendum). `finish_calls` now
raises `MalformedToolCallError`, a subclass of `InferenceError` that says the stream arrived and
the **model's own** tokens will not parse, and the attempt reports `TRUNCATED` only when that error
and a capped completion are both true. The ambiguity this entry waited on is what the pair
resolves: a transport failure on a round after a capped one raises the wide type and keeps its
re-place, and an unparsable call under a backend that reported nothing keeps today's answer too.
The one-line fix this entry warned about was run as a mutation and reddens exactly the case the
warning names.

The shape was reproduced rather than assumed. On a real server, a cap of 20 to 160 tokens on a call
with a long argument streamed 14 to 154 tool-call fragments, closed `finish_reason: "length"`, and
assembled 71 to 899 characters of unterminated JSON; through the shipped adapter and attempt, the
outcome went from `INFERENCE` quoting a JSON decode error to `TRUNCATED` naming the cap.

## Trail

- 2026-08-16: Opened by the finish-reason close, which left this one path where a capped run does
  not reach the settling that reports it.
- 2026-08-17: Landed. The narrower error type is what made the ambiguity answerable, so the entry
  closed on the reading it was waiting for rather than on the one-line fix it warned against, and
  the live arm that reproduces the cut ships beside it
  (`brain/packages/inference/tests/test_cut_tool_call_live.py`). What the close opens is the same
  shape one layer up, the cortex's own turn, where a cut tool call still fails the turn as an
  inference error ([297-cut-tool-call-fails-the-cortex-turn.md](297-cut-tool-call-fails-the-cortex-turn.md)).
