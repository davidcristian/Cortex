# Chat history & sessions (read seam)

Deferrals from the Slice 8.7 session listing and read seam, whose origin decision is
[ADR-0021](../adr/ADR-0021-session-read-seam.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** live-suite fixed-window residual, brain-generated summary titles, session deletion / rename / pinning, paging / cursor, connection indicator + session-title refresh push

**Chat history & sessions in Slice 8.7 ([ADR-0021](../adr/ADR-0021-session-read-seam.md)):** each
behind the unchanged `SessionStore.list_sessions` / `BrainTransport` / `BrainBridge` seams.
- **Bounded end-reads for `list_sessions` landed 2026-07-14 ([ADR-0021 bounded-reads
  addendum](../adr/ADR-0021-session-read-seam.md)); the index cache this entry proposed is
  rejected.** The entry blamed the N round trips (`ZREVRANGE` + N `LRANGE`s) and called the cost
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
  wrong preview that self-heals only on the next message to that chat, a silent-wrong failure mode
  traded for a read that already costs 1 ms. One deliberate behavior change: a corrupt record
  *between* the ends no longer fails a listing (that chat still lists correctly), while `history`
  keeps its fail-loud guarantee and a corrupt record at either end still fails the listing.
- **Auto-restore the most-recent chat on cold start landed 2026-07-12
  ([ADR-0021 addendum](../adr/ADR-0021-session-read-seam.md)).** A new reducer action
  (`adoptSession`, in the line-cap-driven `sessionState.ts` split) hydrates `sessions[0]`'s
  history like `openSession` but mode-preserving (no panel pop) and guarded in the reducer on
  an explicit `touched` flag (a `seq`/`messages` proxy cannot tell an explicit new chat from a
  pristine boot, since `newChat` leaves both pristine): only an untouched overlay adopts, so a
  racing summon, submit, cycle, or explicit new-chat wins and StrictMode's double-fire is
  idempotent; the hook attempts once per mount and a failed history load leaves the fresh chat.
  Gated at 100%; browser-validated in both themes against the demo bridge.
- **The live-Redis session suite sweeps the recency index 2026-07-14 ([ADR-0021 sweep
  addendum](../adr/ADR-0021-session-read-seam.md)).** Its `finally` deleted only
  `cortex:session:{id}:messages` keys, leaving every run's `contract-<uuid>` ids as dangling
  `cortex:sessions` members, and it recorded ids only from checks that RETURNED, so a failing
  check leaked its keys too. Past 50 accumulated members,
  `check_list_sessions_orders_and_summarizes` no longer found its own two sessions inside
  `list_sessions(limit=50)` and failed with a bare `AssertionError`, blaming the adapter for the
  test's residue (observed at 54 stale members). It now sweeps by key pattern plus the index,
  scoped to the `contract-` prefix so real sessions are never touched, after each check and again
  in a `finally`, matching `test_schedule_live.py`; a sweep before the first check heals a store a
  killed run left dirty. The checks return `None`, since sweeping by pattern covers what a raising
  check never reported. **Residual, and no sweep can reach it:** the check still asserts over a
  fixed `limit=50` window with message timestamps fixed in the past, so a live Redis holding 50 or
  more *real* sessions more recent than those crowds it out and fails identically. Fix when it
  bites, by dating the check's messages from a clock or by reading a larger window.
- **Brain-generated summary titles.** Titles derive from the first user message (`summarize_session`);
  a brain-generated summary title would replace that behind the unchanged `SessionSummary`. The
  overlay's own live-title `deriveTitle` stays for a not-yet-persisted chat.
- **Session deletion / rename / pinning.** Write operations on the catalog, a later *gated* surface
  (Slice 6.5 gate + Slice 8.8 Confirmer), out of scope for this read-only slice.
- **Paging / cursor** on `ListSessions` / `GetSessionMessages` if a list or a single history ever
  grows large (a cursor field on the same RPCs); unary snapshots suffice at personal scale.
- **A real connection indicator** and a **session-title refresh push** ride whichever slice first
  streams brain status to the overlay (the ADR-0011 `Health`/status deferral, see
  [body-overlay.md](body-overlay.md)), not this one.
