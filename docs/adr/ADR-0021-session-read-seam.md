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
(reusing the existing record decoder) into `summarize_session`. Equal-timestamp ordering is
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
one keystroke away. Auto-restoring the most-recent chat is a recorded deferral.

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
  port.
- Title/preview truncation lengths live in the core (`TITLE_MAX`/`PREVIEW_MAX`); the overlay's
  own live-title derivation (for a chat not yet persisted) uses the same rule. This is documented so
  the two do not drift. When the brain later generates summary titles ([overlay-ux.md §5](../design/overlay-ux.md)),
  it replaces `summarize_session`'s title behind the unchanged `SessionSummary`.
- The real Tauri `list_sessions`/`session_messages` bridge commands are host-validated glue
  (the overlay's coverage-excluded seam adapter), like the `converse` command; the CI half is
  fakes on both sides.

### Deferred (recorded in the ROADMAP)

- **Per-session first/last/length cache in the index** to drop `list_sessions`' N+1 reads.
- **Auto-restore the most-recent chat on cold start** (this slice opens a new chat; prior chats
  are reachable via switcher/cycling).
- **Brain-generated summary titles** replace `summarize_session`'s title behind the same
  `SessionSummary`.
- **Session deletion / rename / pinning** are write operations on the catalog, a later gated
  surface, out of scope for this read-only slice.
- **Paging / cursor** on `ListSessions`/`GetSessionMessages` if a list or history grows large.
- **A real connection indicator** and **session-title refresh push** join whichever slice first
  streams brain status to the overlay (the ADR-0011 deferral), which is not this one.
