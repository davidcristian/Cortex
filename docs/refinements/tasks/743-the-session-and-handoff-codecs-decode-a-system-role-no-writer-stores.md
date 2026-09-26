# The session and handoff codecs decode a system role no writer stores

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0071](../../adr/ADR-0071-leading-system-messages.md)
**Verified:** 2026-09-26

No brain code writes a system message into a session's history or a handoff's loop tail. History
receives the user's message from `engine.py` and the reply from `engine.py` and `brain_phase.py`,
and a loop tail holds assistant and tool messages only. Both decoders still accept one:
`decode_message` in `cortex_session/store_codec.py` and `_decode_message` in `handoff_codec.py`
build `Role(fields["role"])`, and `system` is a role. Neither `SessionStore` implementation refuses
one in `append`, where both refuse images.

A stored system message that opens the kept history sits next to the turn's own system messages.
On an endpoint whose template takes one leading system message, the adapter then joins it into the
preamble's message ([ADR-0071](../../adr/ADR-0071-leading-system-messages.md)); gemma renders it
as a system turn of its own. Anywhere later in the history, Qwen3.5 and Qwen3.8 raise on it and
Qwen3.6 drops it. Only a hand-edited or tampered store can hold one today.

What would close it: both decoders refuse a system role as a corrupt record and `append` refuses to
store one, with a check in the `SessionStore` contract list that both implementations must pass; or
a recorded decision that the store is trusted with whatever it holds.

## History

- 2026-09-26: filed by the join of leading system messages, which puts a stored system row that
  opens the history into the preamble's message on a joining endpoint.
