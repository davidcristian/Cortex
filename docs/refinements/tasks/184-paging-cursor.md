# Paging / cursor on the read RPCs

**Status:** open, fix when it bites
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** A list or a single history growing large enough that unary snapshots stop sufficing.
**Verified:** 2026-09-11

Paging / cursor on `ListSessions` / `GetSessionMessages` if a list or a single history ever
grows large (a cursor field on the same RPCs); unary snapshots suffice at personal scale.

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
