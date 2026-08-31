# Bounded end-reads for `list_sessions`

**Status:** landed 2026-07-14
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

The index cache this entry proposed is rejected.
The entry blamed the N round trips (`ZREVRANGE` + N `LRANGE`s) and called the cost
negligible; profiling against real Redis found the dominant cost was the read *size*, since
`list_sessions` reused `history()` (`LRANGE 0 -1`) and so shipped and JSON-decoded every message
of every listed chat to index `[0]` and `[-1]`: 4000 records to use 40, listing 20 chats of 200
messages. It now reads exactly what a summary is derived from (`LRANGE 0 0`, `LRANGE -1 -1`,
`LLEN` per listed session, all batched into one transactional pipeline), so the whole listing is
two round trips and two decoded records per chat, removing the N+1 *and* the whole-history read
the entry never named. **23.8 ms to 1.11 ms** measured on that shape against the containerized
Redis; live-Redis contract suite green; CI-gated at 100% with the three new guards
mutation-proven. The `SessionStore` port is unchanged; the core states why the bound is legal
(`summarize_ends(session_id, first, last)`, which `summarize_session` now delegates to). The
proposed cache is rejected outright rather than deferred again: it adds a third `append` write
that is not atomic with the `RPUSH`/`ZADD` pair, so a crash between them leaves a permanently
wrong preview that self-heals only on the next message to that chat, which is a wrong answer nothing
reports, traded for a read that already costs 1 ms. One deliberate behavior change: a corrupt record
*between* the ends no longer fails a listing (that chat still lists correctly), while `history`
keeps its fail-loud guarantee and a corrupt record at either end still fails the listing.

## Trail

- 2026-07-14: The bounded read landed as the [ADR-0021 bounded-reads
  addendum](../../adr/ADR-0021-session-read-seam.md), and the index cache the entry proposed was
  rejected outright. The index counts this entry among the four whose own cost estimate misled
  planning, because it misdiagnosed its own cost and proposed a worse fix than the one that
  shipped.
