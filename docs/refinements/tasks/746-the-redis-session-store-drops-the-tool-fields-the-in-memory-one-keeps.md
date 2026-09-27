# The Redis session store drops the tool fields the in-memory one keeps

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Verified:** 2026-09-28

`encode_message` in `cortex_session/store_codec.py` writes `role`, `text`, `at` and `turn_id` and
nothing else, so `RedisSessionStore.append` drops an assistant message's `tool_calls` and a tool
message's `tool_call_id` without an error. `InMemorySessionStore` keeps the whole `Message`. The two
implementations of one port therefore return different histories for the same appends: an assistant
message with one call, then its tool result, reads back equal from the fake and with no call and no
id from Redis (checked on 2026-09-28 against fakeredis).

No writer stores either field today. History receives the user's message from `engine.py` and a
plain reply from `engine.py` and `brain_phase.py`; the tool loop's messages stay in the turn's
working list or a handoff's loop tail, whose codec keeps both fields. So the contract suite passes
only because no check appends one.

What would close it: `append` refuses a message with tool calls or a tool call id, as it refuses
images and system messages, with a check in the `SessionStore` contract list that both
implementations must pass; or the record format gains both fields.

## History

- 2026-09-28: filed by the close of
  [R-743](743-the-session-and-handoff-codecs-decode-a-system-role-no-writer-stores.md), which made
  both session stores refuse a system message and found this divergence beside it.
