# Paging or a cursor on the read RPCs

**Status:** open, waiting for its trigger
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Trigger:** one reply encodes past 4 MiB, the decoding cap of the body's tonic 0.14.6 client, which
no code under `body/` raises (`max_decoding_message_size` appears nowhere there), while the brain's
server sets no send cap. For `GetSessionMessages` the summed length of the records that
`LRANGE cortex:session:<id>:messages 0 -1` returns is never smaller than the reply, since each
record is JSON with the same four fields and more, with non-ASCII text escaped, so a live reading of
that sum below 4 MiB for every session means the trigger has not fired. For `ListSessions` the reply
holds at most `MAX_SESSION_LIST_LIMIT` (200) recent chats plus every chat kept at the top outside
that window, and that set has no cap in the store.
**Verified:** 2026-09-17

`ListSessions` and `GetSessionMessages` are unary snapshots with no cursor, which is enough at
personal scale. If a single history is the one that grows too large first, the smaller move is a
window on `GetSessionMessagesRequest`: a count of the newest records, mapped to `LRANGE -n -1`,
which is the index arithmetic `list_sessions` already uses. Raising the body's decoding cap instead
only moves the point where one reply fails. Either way the proto change regenerates both committed
stubs.

## History

- 2026-09-11: Checked against the tree; the trigger has not fired. `ListSessionsRequest` still has
  `limit` alone and `GetSessionMessagesRequest` the `session_id` alone (`proto/body.proto:190` and
  `:201`). The servicer clamps the limit to `DEFAULT_SESSION_LIST_LIMIT = 50` and
  `MAX_SESSION_LIST_LIMIT = 200` (`session_rpc.py:27-28`), so a listing is bounded on the wire. A
  history is not: `history` reads `LRANGE 0 -1`
  (`brain/packages/session/src/cortex_session/store.py:128`) and nothing trims the list on append.
  Nothing in the tree measures a history's encoded size, so that is a live reading.
- 2026-09-17: Checked again; the trigger has not fired. One correction: a listing is not bounded by
  the clamp alone, because `list_sessions` (`store.py:213`) returns the newest `limit` chats merged
  with every chat kept at the top, and no cap on that set exists in the session, core or
  orchestrator packages. The rest held, and tonic 0.14.6 sets `DEFAULT_MAX_RECV_MESSAGE_SIZE` to
  4 MiB with the send default at `usize::MAX` (`tonic-0.14.6/src/codec/mod.rs:101-102`). The stored
  record is `encode_message`'s JSON (`store_codec.py:44`), which is why its length bounds the reply.
  No Redis was running, so no session's size was read.
