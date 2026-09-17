# Paging / cursor on the read RPCs

**Status:** open, fix when it bites
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** one reply encodes past 4 MiB, the decoding cap of the body's tonic 0.14.6 client, which
no code under `body/` raises (`max_decoding_message_size` appears nowhere there), while the brain's
server sets no send cap. For `GetSessionMessages` the summed length of the records that
`LRANGE cortex:session:<id>:messages 0 -1` returns is never smaller than the reply, since each
record is JSON carrying the same four fields and more, with non-ASCII text escaped, so a live
reading of that sum below 4 MiB for every session says not fired. For `ListSessions` the reply
holds at most `MAX_SESSION_LIST_LIMIT` (200) recent chats plus every pinned chat outside that
window, and the pinned set has no cap in the store.
**Verified:** 2026-09-17

Paging / cursor on `ListSessions` / `GetSessionMessages` if a list or a single history ever
grows large (a cursor field on the same RPCs); unary snapshots suffice at personal scale.

If a history is the one that bites, the smaller first move is a window on
`GetSessionMessagesRequest`: a count of the newest records, mapped to `LRANGE -n -1`, which is the
index arithmetic `list_sessions` already uses to read a chat's ends. Raising the body's decoding
cap instead only moves the point where one reply fails. Either way the proto change regenerates
both committed stubs.

## Trail

- 2026-09-11: read against the tree and not fired. `ListSessionsRequest` still carries `limit`
  alone and `GetSessionMessagesRequest` the `session_id` alone (`proto/body.proto:190` and
  `:201`), with no cursor field on either. The servicer clamps the limit to
  `DEFAULT_SESSION_LIST_LIMIT = 50` and `MAX_SESSION_LIST_LIMIT = 200` (`session_rpc.py:27-28`),
  so a listing is bounded on the wire. A history is not: `history` reads `LRANGE 0 -1`
  (`brain/packages/session/src/cortex_session/store.py:128`) and nothing trims the list on
  append. The point at which one unary reply stops sufficing is therefore the body's decoding
  cap, which the rpc crate never sets, so it is tonic's default of 4 MiB per message
  (`DEFAULT_MAX_RECV_MESSAGE_SIZE` in tonic 0.14.6). Nothing in the tree measures a history's
  encoded size, so whether any session is near that cap is a live reading.
- 2026-09-17: read against the tree and not fired, with one correction and the trigger restated as
  a reading. The correction: a listing is not bounded by the clamp alone. `list_sessions`
  (`brain/packages/session/src/cortex_session/store.py:213`) returns the newest `limit` chats
  unioned with every pinned chat, so a reply holds up to 200 recent chats plus the pinned ones
  outside that window, and no cap on the pinned set was found in the session, core or orchestrator
  packages. The rest held: `proto/body.proto:190` and `:201` carry no cursor, the clamp is still
  `session_rpc.py:27-28`, `history` still reads `LRANGE 0 -1` at `store.py:128` and `append`
  (`store.py:109`) trims nothing, and tonic 0.14.6 sets `DEFAULT_MAX_RECV_MESSAGE_SIZE` to 4 MiB
  and the send default to `usize::MAX` (`tonic-0.14.6/src/codec/mod.rs:101-102`). The stored
  record is `encode_message`'s JSON (`store_codec.py:44`), which is why its length bounds the
  reply. No Redis was running, so no session's size was read.
