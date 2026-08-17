# A cut tool call fails the cortex turn as an inference error

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first cortex turn observed ending in an inference-failed seam error whose text
quotes a tool call's unterminated arguments.

Opened 2026-08-17 by the tool-call-cut landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) tool-call-cut addendum), which fixed the
delegated half of this shape and left the cortex's own.

A completion cut while the cortex was writing a tool call's `arguments` raises out of
`stream_tool_loop` the same way a delegated one does, and on this path nothing catches it: the
turn task in `converse_stream.py` turns an `InferenceError` into a `SeamError` carrying
`ERROR_CODE_INFERENCE_FAILED` and the error's own text, so the user is told inference failed and
shown a JSON fragment. What the turn would rather say is what it already says when the loop ends
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
