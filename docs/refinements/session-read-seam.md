# Chat history & sessions (read seam)

Deferrals from the Slice 8.7 session listing and read seam, whose origin decision is
[ADR-0021](../adr/ADR-0021-session-read-seam.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** live-suite fixed-window residual, open-chat header title consistency, session pinning, session deletion, paging / cursor

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
  **Landed 2026-07-16 ([ADR-0021 titles addendum](../adr/ADR-0021-session-read-seam.md)), and the
  entry undersold the cost.** The wire/port value `SessionSummary` is unchanged, but "behind the
  unchanged `SessionSummary`" hid four real costs (this backlog's own warning about this area,
  again): a new `SessionStore.set_title` write method, a store-layout change (a
  `cortex:session:{id}:title` string key), a list-read change (`summarize_ends` takes a
  `title_override`, batched into the same pipeline as each chat's two ends), and a tier/timing
  decision. The resident **cortex** generates it on a session's **first turn only**, from the
  opening exchange, and it is persisted **before** `TurnCompleted`. That is what makes it
  hazard-free and race-free: the reply's `stream` has released its GPU lease, so the title call is
  a sequential acquire (never the re-entrant hazard that blocks the reranker), and it needs **no**
  async-port widening (the engine already calls the async `InferenceBackend`); and because the
  title is stored before completion, the overlay's turn-completion refresh already sees the final
  title, so it never rewrites *after* the refresh, which is the race this entry inherited from the
  summon-edge refresh above. A blank/absent title falls back to the first-message derivation, and
  every title is re-bounded to `TITLE_MAX` at read time. Shipped **off by default**
  (`CORTEX_GENERATE_TITLES`): it costs one inference call per new session, and, found live against
  a real reasoning cortex (Qwen 2B), a reasoning model may emit only `reasoning_content` and no
  reply (one case: 13,882 reasoning chars, zero content), so the generated title is empty and the
  first-message title stands. The reasoning-filter and empty-fallback are proven correct by that;
  the finding is that reliable *content* wants thinking disabled or a token cap, which
  `InferenceBackend.stream` cannot yet express (it reopens as a consumer of the disable-thinking /
  token-budget inference deferral, not as new title work). Gated at 100% with four guards
  mutation-proven (title override, first-turn-only, empty title rejected, reasoning ignored).
- **Open-chat header title consistency.** Opened 2026-07-16 behind the landed titles above. The
  switcher now shows the brain title (`SessionSummary.title`), but opening that chat re-derives the
  header from the loaded first user message (`deriveTitle`/`titleFor` in `sessionState.ts`), so the
  header and the switcher row can disagree. `GetSessionMessages` carries messages, not a title, so
  unifying them needs a `title` on that read path (a proto field + overlay plumbing), which a
  brain-contained change cannot deliver. Note the smaller alternative first: the overlay could
  carry the switcher's title into `openSession` when the user picks a row, covering the open path
  without a proto change, but not cold-start adoption or cycling, which load by id.
- **Session deletion / rename / pinning.** Write operations on the catalog, a later *gated* surface
  (Slice 6.5 gate + Slice 8.8 Confirmer), out of scope for this read-only slice.
  **Rename landed 2026-07-16 ([ADR-0021 rename addendum](../adr/ADR-0021-session-read-seam.md)); pin
  and delete deferred as the two entries below.** The entry's "gated ... Confirmer" framing was
  wrong for a management RPC, read against the code: the `SeamConfirmer` (ADR-0022) gates a
  possibly-jailbroken *model*'s tool call **inside a turn** (bound one-per-`Converse`-stream, a
  mid-turn card, tainted turns denied outright); a rename is triggered by the user in the overlay,
  out of band, and its handler is no tool in any registry and never runs through the turn engine, so
  no model/tool/tainted turn can reach it. The gate that fits is **structural user-only
  reachability**, which `RenameSession` has by being a distinct `BrainService` method served off the
  store whose only caller is the overlay's `renameSession` bridge. Rename also needed **no new port
  method**: a user rename *is* `SessionStore.set_title` (the write brain-generated titles built), so
  the slice added only the seam RPC, a bounded handler (`session_rpc`), the not-repeatable body
  transport call, and the switcher rename control. The three verbs were never one change: rename is a
  reversible reuse of an existing write, while pin reshapes the read path and delete cannot yet be
  honest about what it destroys, so the two remain open below.
- **Session pinning.** A new `SessionStore.set_pinned` verb plus a `pinned` field on `SessionSummary`
  across the wire and all four trees, but the real cost is a **read-path** decision the bounded
  two-round-trip listing does not answer: whether a pinned chat escapes the recency `ZREVRANGE`
  window (the expected UX) and so must be unioned into the listing, reshaping the tuned
  `list_sessions`. A genuine design change, not a drop-in behind the write verb, which is why it did
  not ride the rename that landed 2026-07-16.
- **Session deletion.** Destructive and irreversible, and it cannot yet tell the truth about scope: a
  session delete would remove the transcript and catalog entry (a `SessionStore.delete` verb, likely
  a tombstone rather than a hard `DEL` so an in-flight read fails cleanly), but **not** memories
  derived from that session, because `MemoryStore` is `add`/`search` only (no delete verb, the
  separately blocked memory-verbs entry in [memory.md](memory.md)). It also needs an **overlay-local**
  confirm ("are you sure"), since the `SeamConfirmer` gates in-turn tool calls, not a unary
  management RPC (see the rename finding above). Deferred rather than shipped half-honest (implying a
  memory cascade it cannot perform); design it with the memory delete verb and the confirm surface.
- **Paging / cursor** on `ListSessions` / `GetSessionMessages` if a list or a single history ever
  grows large (a cursor field on the same RPCs); unary snapshots suffice at personal scale.
- **A real connection indicator** and a **session-title refresh push** ride whichever slice first
  streams brain status to the overlay (the ADR-0011 `Health`/status deferral, see
  [body-overlay.md](body-overlay.md)), not this one.
  **Both closed 2026-07-16 ([ADR-0021 refresh addendum](../adr/ADR-0021-session-read-seam.md)),
  and the premise they shared was wrong.** Neither needed a status stream. The indicator landed
  by deriving its signal ([body-overlay.md](body-overlay.md)), and this half landed with it: the
  chat list now also refreshes on the **rising edge of visibility**, sharing the one summon latch
  (`useSummonEffect`) with the reminder pull and the connection probe. The two triggers it had,
  mount and turn completion, can both be arbitrarily old by the time anyone looks, since a
  tray-resident body mounts once and the last turn may be days back; and a list that failed to
  load while the brain was down had no way back until a turn completed, which is now the same
  gesture that turns the dot green. **The push itself is not deferred again, because nothing can
  produce it:** session history has exactly one writer, `ConversationEngine` inside a turn
  (`engine.py`), and the schedule ticker dispatches tasks to the task store, never to a session.
  A title therefore cannot change while the overlay watches except through a turn the overlay
  itself ran, which already refreshes on completion. What would reopen it: brain-generated
  summary titles (above), which could rewrite a title *after* the completing turn refreshed the
  list, so that race belongs to that entry.
