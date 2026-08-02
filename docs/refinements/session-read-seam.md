# Chat history & sessions (read seam)

Deferrals from the Slice 8.7 session listing and read seam, whose origin decision is
[ADR-0021](../adr/ADR-0021-session-read-seam.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** live-suite fixed-window residual, out-of-window authoritative title, paging / cursor

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
  **Landed 2026-07-16 as the overlay-only carry ([ADR-0021 header-title addendum](../adr/ADR-0021-session-read-seam.md)),
  and both this entry and the index undersold that option.** The header no longer re-derives
  locally: `openSession` and `adoptSession` read the chat's title from the already-loaded
  `state.sessions` (the same `SessionSummary.title` the switcher row renders) when the chat is in
  the list, falling back to the first-message derivation only when it is not (`headerTitle` in
  `sessionState.ts`). Header and switcher now read one `sessions` snapshot, so they are equal by
  construction, a stronger guarantee than the proto field: a `title` on `GetSessionMessages` is a
  second read that a title change between it and `ListSessions` could desync, and it is more surface
  across four trees for a case the user cannot see (below). The carry closes three disagreements the
  entry named only one of: a user **rename** (default on, always visible, landed the same day) whose
  label the header ignored; a **truncation-length** gap (the brain bounds to `TITLE_MAX` 48, the
  overlay's `deriveTitle` to 32, so a 33-to-48-char first message read longer in the switcher than
  the header); and a **generated title** (behind `CORTEX_GENERATE_TITLES`). The entry's claim that
  the carry misses "cold-start adoption or cycling, which load by id" is wrong read against the code:
  adoption targets `sessions[0]` and cycling targets `cycleTarget(state.sessions, ...)`, so both
  already target a session in `state.sessions`; doing the lookup in the reducer (not threading the
  clicked row's title through the click handler, the narrower shape the entry imagined) covers
  switcher-open, cycling, and adoption alike. Gated at 100% over fakes, with the carry
  mutation-proven (reverting `headerTitle` to the local derivation reddens the switcher-title tests
  in `openSession`, `adoptSession`, and the cold-start hook); browser-validated against the demo
  bridge, live-validated against real Redis (below).
  **The truncation-length third of that claim was itself too broad, and closed 2026-08-03
  ([ADR-0021 truncation addendum](../adr/ADR-0021-session-read-seam.md)).** The carry closed the
  gap for a chat being *loaded*, which is the only kind `headerTitle` sees. It left it open for the
  chat being *had*: `turnState.submit` names a brand-new chat from `deriveTitle` in the same render
  that starts its first turn, and never revisits that header, so the 32 bound survived on the one
  path where the overlay has no brain title to read. The turn-completion refresh then lists the
  chat, and from that moment the header and that chat's own switcher row are two renderings of the
  same first message. Measured in Chromium at 900x900 with the demo bridge extended to list a
  submitted chat the way the brain does: a 42-character first message read in full in the row and
  as `How does the session title trunc…` in the header, both visible together, in a header box of
  339px that fits 42 characters against the row's 314px that fits 39, so the shorter bound was not
  answering less room. The overlay's `TITLE_MAX` is now 48 and `scripts/crosscheck.py` holds the
  two declarations equal, the pair being that gate's third entry and the first in TypeScript.
- **Out-of-window authoritative title.** Opened 2026-07-16 behind the header-title carry above. The
  carry reads the title from `state.sessions`, so a chat **not** in the loaded recency window still
  derives its header locally. The only path today that opens a chat absent from that window is a
  reminder deep-link (`Reminders.tsx` "open chat") to a chat that has fallen outside the loaded
  `listSessions(50)`; the switcher shows no row for such a chat either, so the disagreement is not
  user-visible, which is exactly why the overlay-only carry was preferred over the proto field. The
  authoritative closure is the `title` field on `GetSessionMessages` the entry above named (the same
  read path the reasoning-persistence entry independently wants widened), dead until a consumer that
  opens an out-of-window chat beside the switcher exists (toast activation routing once
  `NotifyRequest` carries a `session_id`, or a search / deep-link by id).
  **Narrowed 2026-08-03 without being closed.** With the two `TITLE_MAX` declarations now equal
  (the addendum recorded above), the local derivation renders exactly what the brain would have
  listed for the same first message, so the fallback no longer differs in *length*. What is still
  open is what it cannot know: a user rename or a generated title stored against that chat, which
  only the read path can carry. Measured on the reminder deep-link in Chromium, a chat outside the
  loaded window opens with its first message derived locally, at the brain's bound.
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
  **Landed 2026-07-16 ([ADR-0021 pinning addendum](../adr/ADR-0021-session-read-seam.md)), and the
  entry named its own crux exactly: the read-path union was the whole item.** A pinned chat DOES
  escape the recency window, so `list_sessions` unions the pinned set into every listing. The tuned
  two-round-trip shape held: round trip one now reads BOTH indexes in one transaction (`ZREVRANGE`
  the recency window AND `SMEMBERS` a new pinned set `cortex:sessions:pinned`), their union
  (recency window first, then pinned ids outside it, deduplicated) is the listed set, and round trip
  two is the same batched ends-read, so it stays two round trips and two decoded records per chat.
  A new pure-core `merge_pinned` is the one shared ordering rule (stable-sort recency then
  `not pinned`, so pinned chats sort above the recency group, newest-active first within each), and
  both the fake and the Redis adapter build the same deduplicated candidate set and hand it there,
  so they cannot drift. Three costs the "verb + field" framing hid: the union is additive, so a
  heavily-pinned catalog lists more than `limit` (bounded by the small pinned set); `delete` must
  also `SREM` the pinned member, or a deleted-then-pinned id lingers as a dangling pin; and
  `set_pinned` takes `*, pinned` keyword-only (the repo's boolean-arg convention). The write RPC
  `SetSessionPinned` has the SAME structural user-only reachability rename/delete got (no tool,
  never through the turn engine); its `SeamMethod` is classified **not repeatable** despite being
  idempotent by value, because the catalog-write convention is uniform (a lost reply must not
  re-assert a pinned value the user's next toggle reversed). The overlay adds a per-row pin toggle
  (a filled-pin indicator doubling as the state), re-lists after the write so the pinned group
  re-forms at the top, and reads the one pinned-first `sessions` order everywhere (switcher, cycling,
  cold-start adoption, which now adopts the top pinned chat when any is pinned). Gated at 100% across
  all four trees, with the union mutation-proven: the flagship contract check pins a chat older than
  a `limit=3` window and asserts it still lists above the recency group (dropping the union reddens
  it), a pinned-and-recent chat is asserted to appear once (dropping the dedup reddens it), and the
  user-only path is pinned by a no-tool structural test. Live-validated (agent, Docker + real Redis):
  four chats seeded with an old one pinned and a `limit=3` listing returned the pinned old chat
  first, above the three newer chats, exactly once.
- **Session deletion.** Destructive and irreversible: a session delete would remove the transcript
  and catalog entry (a `SessionStore.delete` verb, likely a tombstone rather than a hard `DEL` so an
  in-flight read fails cleanly). The memory-cascade half is **no longer blocked on a missing verb**:
  it landed 2026-07-16 as `MemoryStore.delete_scope(scope)` ([memory.md](memory.md),
  [ADR-0008](../adr/ADR-0008-memory-v1.md)), so a delete can cascade to a session's derived memories
  by their scope. It cascades honestly **only under session scoping** (`SessionMemoryScope`, where
  `scope == session_id`); under the default global scope a session's memories are the shared
  cross-conversation space, so there is nothing session-private to cascade and the cascade must
  **not** pass `GLOBAL_SCOPE`. The entry still needs an **overlay-local** confirm ("are you sure"),
  since the `SeamConfirmer` gates in-turn tool calls, not a unary management RPC (see the rename
  finding above). Still deferred: design the `SessionStore.delete` verb, the scope-aware cascade, and
  the confirm surface together.
  **Landed 2026-07-16 ([ADR-0021 delete addendum](../adr/ADR-0021-session-read-seam.md)), and the
  entry's one guess it got wrong was the tombstone.** All three halves shipped together as the entry
  asked. The `SessionStore.delete(session_id)` verb is a **hard** delete, not a tombstone: read
  against the code, the reads are stateless snapshots and an unknown session already reads as an
  empty `history`, so a deleted chat degrades cleanly with **no** in-flight id to protect (the same
  reasoning the same-day `delete_scope` hard delete turned on), and a privacy-motivated "forget this
  chat" wants true erasure, not a hidden-but-kept transcript. The Redis adapter drops all three keys
  a chat can hold, the `:messages` list, the `:title` string, and the `cortex:sessions` recency-index
  member, in one transactional pipeline, leaving nothing orphaned, and is idempotent. The scope-aware
  cascade is **not** on the turn-facing `MemoryRecaller` (that would put a forget verb on the turn,
  which `test_the_recaller_exposes_no_forget_verb...` forbids) but on a separate trusted
  `SessionMemoryCascade(store, scope)` the orchestrator wires into `DeleteSession` only. It targets
  `write_scope(session_id)` and cascades **only** when that scope is the session's own private space
  (`scope == session_id`); the `GLOBAL_SCOPE` guard is checked **first**, so `GLOBAL_SCOPE` can never
  reach `delete_scope` even for a session whose id equals `GLOBAL_SCOPE` (the flagship distrust-green
  test seeds exactly that and reddens when the guard is dropped). The confirm is **overlay-local** as
  the entry said: the switcher row's trash swaps in an inline "Delete this chat?" confirm/cancel pair,
  and `onDelete` fires only on the second, explicit click. The gate is the **same structural
  user-only reachability** rename got: `DeleteSession` is a `BrainService` method the overlay drives,
  no tool in any registry, never through the turn engine (`SeamMethod::DeleteSession` classified NOT
  repeatable, the body making exactly one attempt at a destroy). The overlay also handles the
  **current-session hazard**: deleting the open chat tears down its in-flight turn (so a streaming
  reply cannot re-materialize the chat with a post-delete `append`) and falls back to a fresh new
  chat, never rendering a deleted transcript. Gated at 100% across all four trees; live-validated
  against real Redis + pgvector (every key gone, the recency member gone, session-scoped memories
  gone, a global-scoped memory spared).
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
