# Bounded end-reads for `list_sessions`

**Status:** done 2026-07-14
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

The entry blamed the N round trips (`ZREVRANGE` plus N `LRANGE`s) and called the cost negligible.
Profiling against real Redis found the dominant cost was read size: `list_sessions` reused
`history()` (`LRANGE 0 -1`), so it transferred and JSON-decoded every message of every listed chat
to index `[0]` and `[-1]`, which is 4000 records to use 40 when listing 20 chats of 200 messages.

It now reads exactly what a summary is derived from (`LRANGE 0 0`, `LRANGE -1 -1` and `LLEN` per
listed session, batched into one transactional pipeline), so a listing is two round trips and two
decoded records per chat. Measured on that shape against the containerized Redis: 23.8 ms to
1.11 ms. The `SessionStore` port is unchanged; the core states why the bound is legal
(`summarize_ends(session_id, first, last)`, which `summarize_session` delegates to).

The index cache the entry proposed is rejected outright rather than deferred. It adds a third
`append` write that is not atomic with the `RPUSH`/`ZADD` pair, so a crash between them leaves a
permanently wrong preview that only corrects itself on the next message to that chat, which is a
wrong answer nothing reports, traded against a read that already costs 1 ms.

One deliberate behaviour change: a corrupt record between the ends no longer fails a listing, while
`history` still fails loudly and a corrupt record at either end still fails the listing.

## History

- 2026-07-14: Closed as [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md) decision 7. It is one
  of the four entries whose own cost estimate misled planning: it misdiagnosed its own cost and
  proposed a worse fix than the one that shipped.
