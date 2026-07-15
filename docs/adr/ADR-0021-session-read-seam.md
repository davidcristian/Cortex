# ADR-0021: Store-backed chat history & cycling over the session-read seam

- **Status:** Accepted (Slice 8.7)
- **Date:** 2026-07-06

## Context

The overlay (Slice 8, [ADR-0011](ADR-0011-body-v1.md)) is a *view* of store-backed
conversation state. A chat is a `session_id`, and the brain persists that session's messages
in the `SessionStore` (the one hard rule). But the seam only carries per-turn `Converse`: the
overlay can *write* a session (stream a turn) and re-render the streams it saw, yet it cannot
*read back* the store. So today it keeps the current app run's chats in memory
([overlay-ux.md §5](../design/overlay-ux.md)). That is one live session, lost on restart, no chat
list, no cross-restart cycling. The design named this gap and scheduled it here.

This slice closes it: two **read-only** RPCs that expose views of the durable store, threaded
through the brain service, the body's `BrainTransport` port, and the overlay's `BrainBridge`
port, so the chat list, the switcher, and `Ctrl+↑/↓` cycling load from the store instead of
memory. It is additive and orthogonal to the OS-action track, with no `Converse` change, no new
write path, nothing that touches the hard rule beyond *reading* what the store already holds.

## Decision

### 1. Two read-only unary RPCs on `BrainService`

Extend [proto/body.proto](../../proto/body.proto) (v0 field numbers frozen, so extend, never
renumber):

```proto
rpc ListSessions(ListSessionsRequest) returns (ListSessionsReply);
rpc GetSessionMessages(GetSessionMessagesRequest) returns (GetSessionMessagesReply);

message ListSessionsRequest { int32 limit = 1; }          // 0 = server default
message ListSessionsReply { repeated SessionSummary sessions = 1; }
message SessionSummary {
  string session_id = 1;
  string title = 2;                 // derived: first user message, one line, truncated
  string preview = 3;               // derived: last message text, one line, truncated
  int64 last_activity_unix_ms = 4;  // for a relative timestamp in the switcher
}

message GetSessionMessagesRequest { string session_id = 1; }
message GetSessionMessagesReply { repeated SessionMessage messages = 1; }
message SessionMessage {
  string role = 1;      // "user" | "assistant" (the only persisted roles)
  string text = 2;
  string turn_id = 3;
  int64 at_unix_ms = 4;
}
```

Both are **unary** (a list and a history are snapshots, not streams) and read-only. They
expose views of state the store already owns, add no write path, and so cannot violate the
hard rule. They ride the existing seam-token interceptor (ADR-0016) unchanged: it fronts every
method, current and future. Timestamps cross the wire as `int64` unix-milliseconds rather than
a `google.protobuf.Timestamp` import. The overlay needs a number to compute a relative age,
and the store's tz-aware `datetime` collapses to an instant losslessly for that purpose.

### 2. `SessionStore.list_sessions` (the one new port method); `GetSessionMessages` reuses `history`

`GetSessionMessages` is exactly `SessionStore.history(session_id)` mapped to the wire, with no new
port method: the persisted history already contains only the `USER`/`ASSISTANT` dialogue
(`SYSTEM`/`TOOL` are per-turn, never stored ([conversation.py](../../brain/packages/core/src/cortex_core/conversation.py))).

Listing needs the one genuinely new capability of enumerating sessions ordered by recency,
which the per-session list layout cannot answer. So `SessionStore` gains:

```python
async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]: ...
```

returning at most `limit` summaries, **most-recently-active first**. `SessionSummary` is a
pure-core value (`cortex_core/sessions.py`):

```python
@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    title: str
    preview: str
    last_activity: datetime   # tz-aware; the orchestrator maps it to unix-ms at the seam
```

### 3. Summarization is pure core; enumeration+ordering is the adapter's

Deriving a title/preview is domain logic, so it lives in the core, not the adapter (the
hexagonal invariant that adapters translate and hold no business logic). A pure
`summarize_session(session_id, messages) -> SessionSummary` (`sessions.py`) takes a session's
messages and derives:

- **title** is the first message's text (index 0 is always the first user message: the engine
  appends the user turn first and only `USER`/`ASSISTANT` persist), collapsed to one line and
  truncated to `TITLE_MAX`;
- **preview** is the last message's text, one line, truncated to `PREVIEW_MAX`;
- **last_activity** is the last message's `at`.

Both `InMemorySessionStore` and `RedisSessionStore` build their summaries through this same
function, so the derivation rule cannot drift between the fake and the real adapter, and the
shared contract test pins it once. The adapter's own job stays pure translation: enumerate
sessions newest-first, fetch each session's messages, call `summarize_session`.

**Redis layout.** A sorted set `cortex:sessions` scored by each session's last-activity unix
time is maintained on `append` (one `ZADD` alongside the existing `RPUSH`, score = the
message's `at`; the last append wins, so the score tracks last-activity). `list_sessions` does
`ZREVRANGE cortex:sessions 0 limit-1` for the newest ids, then one `LRANGE`+decode per id
(reusing the existing record decoder) into `summarize_session`. (That per-id read became a
bounded two-ended one in 2026-07-14's addendum below.) Equal-timestamp ordering is
unspecified (Redis orders equal scores lexicographically; the fake by insertion), but the switcher
does not depend on it, and the contract test uses distinct timestamps.

### 4. Orchestrator: two handlers on `BrainService`, the store injected alongside the engine

`BrainService` takes the `SessionStore` explicitly (`create_server`/`serve`/`run_from_env`
thread the same instance they already build for the engine), so the read RPCs read the store
directly, since they are reads, not turns, and must not go through the turn engine. The handlers
map core→wire and clamp the request: `limit ≤ 0` → `DEFAULT_SESSION_LIST_LIMIT` (50), capped at
`MAX_SESSION_LIST_LIMIT` (200). A `SessionStoreError` aborts the unary RPC with
`UNAVAILABLE` (the body surfaces it as `TransportError::Rpc`), mirroring the `Converse`
`session_store_unavailable` semantics for a streaming turn.

### 5. Body & overlay ports grow with typed reads; the overlay owns the session id

`body_core::BrainTransport` gains `list_sessions(limit)` and `session_messages(session_id)`
returning `Vec<SessionSummary>` / `Vec<SessionMessage>` (new pure core structs), implemented on
`BrainSeamClient` as unary calls reusing the existing `status_to_error` mapping; the in-process
fake-brain contract test serves them. The overlay's `BrainBridge` grows the mirror
`listSessions`/`sessionMessages` (real Tauri commands are host-validated glue; the CI-gated
overlay logic drives the fake).

The overlay's session id moves from a fixed `main.tsx` prop into `useOverlay` state (minted via
an injected factory, default `crypto.randomUUID`), so multi-chat is real:

- **New chat** (`＋` / `Ctrl+N`) mints a fresh id and clears the panel; the prior chat is
  already persisted.
- **The chat list** loads via `listSessions` on mount and refreshes when a turn completes (a
  finished turn is now a listable session).
- **The switcher** (`⌄`) shows the list (title + relative time + preview); selecting a chat
  loads its history via `sessionMessages`.
- **Cycling** (`Ctrl+↑`/`Ctrl+↓`) walks the list newest-first (a pure `cycleTarget` helper),
  clamped at the ends (no wrap), loading the target's history.

Reducer state (`sessionId`, `sessions`, `switcherOpen`) and the cycle math stay in the pure
`overlayState` reducer (100%-tested); the async bridge calls live in `useOverlay`; animation
stays in CSS.

**Cold start opens a new chat.** Persisted chats are reachable via the switcher and cycling,
not auto-restored into the panel on launch. That is simpler and fully testable, and the switcher is
one keystroke away. Auto-restoring the most-recent chat is a recorded deferral (landed
2026-07-12; addendum below).

## Alternatives rejected

- **A streaming `ListSessions` / paged history.** A personal assistant's recent-chat list and
  a single session's history are small and bounded; unary snapshots are simpler and match the
  overlay's load-then-render shape. Paging fits behind the same RPCs (a cursor field) if a
  session ever grows unwieldy.
- **The adapter returns pre-derived title/preview.** Puts domain logic (truncation, first-user
  selection) in the adapter, violating the hexagonal invariant and letting the fake and Redis
  derivations drift. Rejected for the pure `summarize_session` both call.
- **The store returns raw `(session_id, last_activity)` refs; the core loads each history via
  `history()` and summarizes.** Cleanest hexagonally but makes the *consumer* issue N+1 calls
  across the port and re-reads full histories the adapter is already positioned to read once.
  Keeping the N+1 inside the adapter (which owns the layout) is the better seam; the port stays
  a single `list_sessions` returning domain values.
- **`google.protobuf.Timestamp` for `last_activity`.** A well-known-type import for a value the
  overlay immediately converts to a millisecond number for relative-age math. `int64` unix-ms
  is dependency-free and sufficient.
- **A separate `SessionCatalog` port.** Listing is a read over the same session state the
  `SessionStore` owns; a second port would split one responsibility across two seams for no
  gain.

## Consequences

- The overlay becomes a true view of the durable store: chats survive restarts, the switcher
  and cycling are real, and history loads from Redis. The hard rule already guaranteed the
  data was there; this slice only lets the body read it.
- `list_sessions` costs one `ZREVRANGE` + N `LRANGE`s (N ≤ limit). For a personal system's
  recent list this is negligible; caching each session's first/last message and length in the
  index to drop the per-session reads is a **deferred** perf refinement behind the unchanged
  port. (Superseded 2026-07-14, bounded-reads addendum below: the per-session read is now the
  chat's two ends, batched into one transaction, and the cache is rejected.)
- Title/preview truncation lengths live in the core (`TITLE_MAX`/`PREVIEW_MAX`); the overlay's
  own live-title derivation (for a chat not yet persisted) uses the same rule. This is documented so
  the two do not drift. When the brain later generates summary titles ([overlay-ux.md §5](../design/overlay-ux.md)),
  it replaces `summarize_session`'s title behind the unchanged `SessionSummary`.
- The real Tauri `list_sessions`/`session_messages` bridge commands are host-validated glue
  (the overlay's coverage-excluded seam adapter), like the `converse` command; the CI half is
  fakes on both sides.

### Deferred (recorded in the ROADMAP)

- **Per-session first/last/length cache in the index** to drop `list_sessions`' N+1 reads:
  **rejected 2026-07-14** (bounded-reads addendum below) in favor of reading each chat's two
  ends in one batch, which removes the N+1 without a second copy of the data.
- **Auto-restore the most-recent chat on cold start** landed 2026-07-12 (addendum below).
- **Brain-generated summary titles** replace `summarize_session`'s title behind the same
  `SessionSummary`.
- **Session deletion / rename / pinning** are write operations on the catalog, a later gated
  surface, out of scope for this read-only slice.
- **Paging / cursor** on `ListSessions`/`GetSessionMessages` if a list or history grows large.
- **A real connection indicator** and **session-title refresh push** join whichever slice first
  streams brain status to the overlay (the ADR-0011 deferral), which is not this one.

## Addendum on live validation (agent, 2026-07-07)

Validated the brain half end to end against the **real brain + Redis** via Docker (no GPU, since the
reads never touch a model; the echo backend served the seeding turn), per the working rhythm
(Docker/backend validation is the agent's; only OS-native Rust/Tauri is host-only):

- **Full-seam round-trip**, `body/crates/rpc/tests/live.rs::session_reads_round_trip_over_the_live_seam`
  (`#[ignore]`d, run with `cargo test -p body-rpc --test live -- --ignored`): it seeds one turn over
  `Converse` (persisting a session to real Redis), then reads it back over the typed `BrainTransport`
  where `ListSessions` returns the chat with its derived title (the first user message) and a real
  last-activity timestamp, and `GetSessionMessages` returns the user turn + assistant reply in order.
  This exercises the `cortex:sessions` ZSET index, `list_sessions`, `summarize_session`, the
  orchestrator handlers, and the gRPC seam against live backends.
- **Store contract against live Redis.** `uv run pytest -m integration --no-cov packages/session`
  passed, so the shared `list_sessions` contract check (recency ordering + title/preview derivation)
  holds on real Redis, not just fakeredis.

Both green. The overlay chrome is browser-validated (CI-gated, 77 tests); the Windows-native Tauri
`list_sessions`/`session_messages` commands remain host validation.

Environment note: the Docker build needed a clean `DOCKER_CONFIG` (the host `~/.docker/config.json`'s
`credsStore: "desktop.exe"` is unreachable from the WSL shell and breaks the BuildKit frontend pull).

## Addendum (2026-07-12): cold start adopts the most recent chat

The auto-restore deferral lands as the hook-effect refinement the decision anticipated, with one
design point worth recording: the existing `openSession` action could not be reused. Its
reducer unconditionally raises the panel (a background restore must never pop UI) and its hook
callback cancels the in-flight turn and denies pending confirms (correct for a user click,
destructive for a background adopt). So adoption is its own reducer action, `adoptSession`
(`sessionState.ts`, split from `overlayState.ts` for the line cap): it hydrates exactly like
`openSession` but preserves `mode`, and it no-ops unless the overlay is untouched. The guard
is an explicit `touched` flag (set by open/submit/new-chat/cycle), **not** a `seq`/`messages`
proxy: an adversarial review found that `newChat` leaves both at their pristine values, so
open then new-chat then dismiss reads as a boot-fresh `{hidden, [], seq 0}` and the proxy
would hijack the explicitly chosen fresh chat. The flag distinguishes them, so a racing summon,
submit, cycle, or explicit new-chat always wins. The guard is evaluated in the reducer at
dispatch time (StrictMode's double-fired mount effect stays idempotent); the hook adds a
one-attempt-per-mount ref so a later newest-session change (a completed turn) never triggers a
redundant adopt fetch, and a failed history load leaves the fresh chat (the `openSession`
rule). Gated at 100% through the existing FakeBridge harness (including the exact new-chat
hijack scenario and the latch's fetch count); browser-validated against the demo bridge in
both themes (launch lands in the restored chat, hidden until summoned). The real-bridge leg
rides the unchanged `BrainBridge`, so nothing below the hook changed.

## Addendum (2026-07-14): `list_sessions` reads only each chat's two ends

The deferred perf refinement lands, but **not** as the cache this ADR proposed, because the
cost it named was the smaller half of the real one.

**What the cost actually was.** This ADR blamed the N round trips (`ZREVRANGE` + N `LRANGE`s)
and proposed caching each session's first/last/length in the index to remove them. Profiling
against real Redis says otherwise: the dominant cost was the read *size*, not the trip count.
`list_sessions` reused `history()`, i.e. `LRANGE key 0 -1`, so listing 20 chats of 200 messages
shipped and JSON-decoded 4000 records to use 40 of them, all to index `[0]` and `[-1]`.

**Decision: bound the reads instead.** A summary is derived from a chat's two ends and nothing
between them, so the adapter now fetches exactly that: per listed session `LRANGE key 0 0`,
`LRANGE key -1 -1`, and `LLEN key`, with every listed session's three reads queued into **one
transactional pipeline**. The whole listing is two round trips (the index, then the ends) and
two decoded records per chat, so it removes the N+1 the deferral was about *and* the whole
history read it did not name. That the derivation needs only the ends is stated in the core as
`summarize_ends(session_id, first, last)`, with `summarize_session` delegating to it, so the
rule that licenses the bounded read lives with the rule it implements and both stores still
derive summaries through the core (the fake keeps calling `summarize_session`; nothing about
the `SessionStore` port changes).

The `LLEN` is not incidental: it gives the tail record its true index, so a corrupt last record
is still named by its real position (`index 199`, not the position it landed at in the read).
It rides the same transaction as the pair so the length and the record it names are one
snapshot: unbatched, an append landing between the two reads would make the length describe a
record the listing never saw.

**The cache is rejected outright**, not deferred again. It would add a third write to `append`
(after the `RPUSH` and the `ZADD`) that is not atomic with them, so a crash between them leaves
a preview that is **permanently wrong** and self-heals only on the next message to that chat, a
silent-wrong failure mode traded for a read that is already 1 ms. It also duplicates state the
list itself holds, which is the kind of derived-copy invariant that rots. Bounded reads need no
new state at all.

**One deliberate behavior change.** A listing no longer decodes the middle of a chat, so a
corrupt record between the ends can no longer take the whole chat list down; the affected chat
still lists (with correct title and preview). `history` is untouched and still fails loudly on
that record, so the guarantee that matters (the context a turn is built from is never silently
truncated) is exactly where it was. A corrupt record at either **end** still fails the listing
loudly, so this is a narrower blast radius, not a new tolerance for corruption. The dangling
index entry (empty list) stays skipped, as before.

**Evidence (agent, Docker + real Redis).**
- Benchmark, 20 sessions of 200 messages against the containerized Redis: **23.8 ms to 1.11 ms**
  (about 21x) for the same `list_sessions(limit=50)` call, comparing the shipped implementation
  against a replica of the previous one on the same seeded data.
- The live-Redis contract suite (`uv run pytest -m integration --no-cov packages/session`)
  passes, so the recency ordering and title/preview derivation hold on real Redis, not only on
  fakeredis.
- CI-gated at 100% over fakeredis, with the three new guards mutation-proven (reverting each
  individually turns exactly its test red): the tail index derived from `LLEN` (fixing it to the
  read position mis-names the record), the wrapping covering the batched read (a `WRONGTYPE`
  inside the pipeline escapes unwrapped when it does not), and the ends-only read itself (a
  corrupt middle record fails the listing when the whole history is read).

Remaining deferred here: nothing on this path. Paging (below) is still the answer if a *list*
ever grows large, since the bound is per chat, not on the number of chats listed.

## Addendum (2026-07-14): the live suite sweeps the recency index, per check

The live-Redis suite polluted the store it validated. Its `finally` deleted only the
`cortex:session:{id}:messages` keys, never the `cortex:sessions` members `append` writes
alongside them, so every run left its `contract-<uuid>` ids as dangling index entries. It also
collected ids from `used_session_ids += await check(store)`, which records them only once a
check RETURNS, so a check that failed leaked its keys as well.

Those two compound into a suite that breaks itself. `check_list_sessions_orders_and_summarizes`
asserts over `list_sessions(limit=50)`, filtered to the two sessions it just created. Once the
accumulated dangling members push past 50, its own sessions fall outside the window and the check
fails with a bare `AssertionError`, blaming the adapter for the test's own residue. Observed with
54 stale `contract-*` members; removing them by hand made the suite green, which is the tell.

`tests/test_schedule_live.py` already had the right shape, so the fix is to match it: a `_sweep`
that deletes by key pattern **and** removes prefix-matching members from the index, running after
each check and again in a `finally`. Sweeping by pattern rather than by returned ids is the
substance of it, since a pattern covers what a raising check never got to report. The checks now
return `None`, no caller wanting the ids. A sweep also runs before the first check, so a run that
was killed outright heals the store instead of poisoning the next run. Prefix scoping is what
keeps this safe on a shared server: real sessions are never matched, so unlike the schedule suite
this one still needs no skip.

**Evidence (agent, Docker + real Redis).** Seeding 60 stale `contract-*` members reproduces the
reported failure on the old code exactly (bare `AssertionError` on the ordering assert), and that
failing run leaks 2 more message keys, confirming the second defect. The fixed suite passes
against the same poisoned catalog and leaves 0 contract keys and 0 contract members behind, with
the pre-existing real sessions untouched. Injecting a failure into a mid-suite check leaves the
same 0 and 0.

Remaining deferred here: the check still reads a fixed `limit=50` window with message timestamps
fixed in the past, so a live Redis holding 50 or more *real* sessions more recent than those
crowds it out and fails the same way. That needs the check to date its messages from a clock, or
to read a larger window; it is not reachable by any sweep, which must leave real sessions alone.
