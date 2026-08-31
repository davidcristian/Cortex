# A cut tool call fails the cortex turn as an inference error

**Status:** landed 2026-08-20
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-17 by the tool-call-cut landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) tool-call-cut addendum), which fixed the
delegated half of this shape and left the cortex's own.

A completion cut while the cortex was writing a tool call's `arguments` raises out of
`stream_tool_loop` the same way a delegated one does, and on this path nothing catches it: the turn
task in `converse_stream.py` turns an `InferenceError` into a `SeamError` carrying
`ERROR_CODE_INFERENCE_FAILED` and the error's own text, so the user is told inference failed and
shown a JSON fragment. What the turn should say instead is what it already says when the loop ends
normally on a capped completion, `REPLY_CAPPED_NOTE` under the text it did produce.

The narrower `MalformedToolCallError` and the `StopLedger` the turn already passes are both in
place, so the pair that settles it exists; what does not is a decision about the surface. The
delegated path answers with an outcome, and the cortex path is a live stream whose partial text has
already been sent, so ending it with the capped note means catching mid-stream and persisting the
fragment, which is `BRAIN_FAILED_NOTE`'s shape rather than the note's. That is a turn-engine change
with a store write in it, not the one-line arm the delegated fix was.

It is also rarer here than it was there. A user's turn sends no `max_tokens` unless a deployment
set `CORTEX_REPLY_MAX_TOKENS`, so the only limit that can cut it is the context window, and the cut
has to land inside the few tokens of a tool call's arguments rather than anywhere in a long reply.

## Trail

- 2026-08-20: Landed (ADR-0005 cortex-cut addendum). `handle_turn` gained an
  `except MalformedToolCallError` arm that flushes the guarded channels, streams the note the
  `StopLedger` picks, and falls through to the one persist path, so the turn persists once and
  completes rather than raising. Two things this entry had wrong are worth recording. It called
  the delegated fix a one-line arm; that fix is twenty-four lines and returns a value where this
  one lets a store write run, which is the difference that made the control flow worth re-deriving
  rather than copying. And the capped note is only half the answer: an unparsable call with no cap
  reported is a model breaking its own grammar, so a second note, `UNREADABLE_CALL_NOTE`, says
  that without naming a bound that was never reached, and the two helpers read the same boolean
  and disagree on it by construction. The deep model's phase still reads this as a dead server,
  which is opened as [R-340](340-the-deep-phase-cannot-see-a-cut-call.md).
