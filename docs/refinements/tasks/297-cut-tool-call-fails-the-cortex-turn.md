# A cut tool call fails the cortex turn as an inference error

**Status:** done 2026-08-20
**Area:** inference-model-manager
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

Opened 2026-08-17 by the fix for a cut tool call
([ADR-0048](../../adr/ADR-0048-generation-bounds.md)), which covered the delegated half of this
shape and left the cortex's own.

A completion cut while the cortex was writing a tool call's `arguments` raises out of
`stream_tool_loop` the same way a delegated one does, and nothing on this path caught it: the turn
task in `converse_stream.py` turned an `InferenceError` into a `SeamError` with
`ERROR_CODE_INFERENCE_FAILED` and the error's own text, so the user was told inference failed and
shown a JSON fragment. What the turn should say is what it already says when the loop ends normally
on a capped completion, `REPLY_CAPPED_NOTE` under the text it did produce.

It is rarer here than on the delegated path. A user's turn sends no `max_tokens` unless a
deployment set `CORTEX_REPLY_MAX_TOKENS`, so the only limit that can cut it is the context window,
and the cut has to fall inside the few tokens of a tool call's arguments.

## History

- 2026-08-20: Done (ADR-0048). `handle_turn` gained an `except MalformedToolCallError` branch that
  flushes the guarded channels, streams the note the `StopLedger` picks, and falls through to the
  one persist path, so the turn persists once and completes rather than raising. Two things this
  entry had wrong are worth recording. It called the delegated fix a one-line branch; that fix is
  twenty-four lines and returns a value where this one lets a store write run, which is why the
  control flow was worked out again rather than copied. And the capped note is only half the
  answer: an unparsable call with no cap reported is a model breaking its own grammar, so a second
  note, `UNREADABLE_CALL_NOTE`, says that without naming a bound that was never reached, and the
  two helpers read the same boolean and cannot both apply. The deep model's phase still reads this
  as a dead server, opened as [R-340](340-the-deep-phase-cannot-see-a-cut-call.md).
