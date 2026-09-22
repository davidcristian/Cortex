# ADR-0021: Store-backed chat history and cycling over read-only session RPCs

**Status:** Accepted (2026-08-06)

## Context

The overlay ([ADR-0011](ADR-0011-body-v1.md)) is a view of store-backed conversation state: a chat
is a `session_id` whose messages the brain persists in the `SessionStore`. The wire contract had
only the per-turn `Converse`, so the overlay could write a session but not read the store back; it
kept one run's chats in memory and lost them on restart.

This decision exposes read-only views of the store, so the chat list, the switcher and cycling load
from Redis, and then adds the catalog's limited listing, generated titles, and the user's rename,
delete and hoist writes.

## Decision

### 1. Two read-only unary RPCs on `BrainService`

[proto/body.proto](../../proto/body.proto) has `ListSessions(ListSessionsRequest)` and
`GetSessionMessages(GetSessionMessagesRequest)`. `ListSessionsRequest.limit` of 0 means the server
default. A `SessionSummary` has `session_id`, `title`, `preview`, `last_activity_unix_ms` and
`hoisted` (decision 12); a `SessionMessage` has `role` (`user` or `assistant`, the only persisted
roles), `text`, `turn_id` and `at_unix_ms`. Both RPCs are unary, because a list and a history are
snapshots, and read-only, so they add no write path and cannot violate the hard rule. They pass
through the token interceptor ([ADR-0016](ADR-0016-shared-token.md)) unchanged. Timestamps cross as
`int64` unix milliseconds: the overlay needs a number to compute a relative age, and the store's
tz-aware `datetime` collapses to that instant without loss.

### 2. `SessionStore.list_sessions` is the new port method; `GetSessionMessages` reuses `history`

`GetSessionMessages` is `SessionStore.history(session_id)` mapped to the wire. The persisted
history holds only the `USER` and `ASSISTANT` dialogue, since `SYSTEM` and `TOOL` messages are
per-turn and never stored (`cortex_core/conversation.py`). Listing sessions by recency is the one
new capability, so the port gains `async list_sessions(*, limit) -> Sequence[SessionSummary]`, most
recently active first. `SessionSummary` is a frozen pure-core value in `cortex_core/sessions.py`,
its `last_activity` a tz-aware `datetime`.

### 3. Summarization is pure core; listing and ordering are the adapter's

Deriving a title and a preview is domain logic, so it lives in the core.
`summarize_ends(session_id, first, last, *, title_override, hoisted)` derives the title from the
first message (always the first user message, since the engine appends the user turn first), the
preview from the last message, and `last_activity` from the last message's `at`;
`summarize_session` delegates to it. Both stores build summaries through these functions, so the
rule cannot diverge between the fake and the Redis adapter, and the shared contract test asserts it
once. `PREVIEW_MAX` is 96 characters; the title limit is decision 14.

The Redis adapter keeps a sorted set `cortex:sessions` scored by last activity, maintained by one
`ZADD` beside the `RPUSH` on every `append`, so the last append's `at` wins. Ordering of equal
timestamps is unspecified (Redis orders equal scores lexicographically, the fake by insertion); the
switcher does not depend on it and the contract test uses distinct timestamps.

### 4. The orchestrator serves the reads straight off the store

`BrainService` takes the `SessionStore` explicitly, because these are reads rather than turns and
must not go through the turn engine. The handlers (`cortex_orchestrator/session_rpc.py`) map core to
wire and clamp the request: `limit ≤ 0` becomes `DEFAULT_SESSION_LIST_LIMIT` (50), capped at
`MAX_SESSION_LIST_LIMIT` (200). A `SessionStoreError` aborts the RPC with `UNAVAILABLE`, which the
body reports as `TransportError::Rpc`.

### 5. Body and overlay ports gain typed reads; the overlay holds the session id

`body_core::BrainTransport` gains `list_sessions(limit)` and `session_messages(session_id)`,
implemented on `BrainSeamClient` as unary calls through the shared status mapping, and served by
the in-process fake brain in the contract test. The overlay's `BrainBridge` mirrors them as
`listSessions` and `sessionMessages`. The session id is `useOverlay` state, created by an injected
factory (default `crypto.randomUUID`):

- **New chat** (`＋` or `Ctrl+N`) creates a fresh id and clears the panel.
- **The chat list** loads on mount, after a turn completes, and on each summon (decision 8).
- **The switcher** (`⌄`) shows each chat's title, relative time and preview; selecting one loads
  its history. Its rows' roles and what a switch announces are decisions 8 and 13 of
  [ADR-0052](ADR-0052-overlay-focus-and-announcements.md).
- **Cycling** (`Ctrl+↑`/`Ctrl+↓`) walks the list in its listed order through the pure
  `cycleTarget`, clamped at the ends with no wrap, and moves no focus.

The session state and the cycle arithmetic live in pure reducers; the bridge calls live in hooks.

### 6. Cold start adopts the most recent chat

On launch the overlay loads the list and adopts its first row: the topmost hoisted chat when the
list has one, the newest chat otherwise. Adoption is its own reducer action, `adoptSession`
(`overlay/sessionState.ts`), because `openSession` raises the panel and its hook cancels the
in-flight turn and denies pending confirms, which a background restore must never do.
`adoptSession` hydrates like `openSession`, keeps `mode`, and applies only while an explicit
`touched` flag is unset. Open, submit, new chat, cycle and summon set it, so any user action wins
the race; deriving it from `seq` or `messages` would not, since `newChat` leaves both untouched.
The hook makes one attempt per mount, and a failed history load leaves the fresh chat.

### 7. A listing reads only each chat's two ends

A summary is derived from a chat's first and last messages, so `list_sessions` reads those and
nothing between: per listed session `LRANGE key 0 0`, `LRANGE key -1 -1`, `LLEN key` and
`GET :title`, all queued into one transactional pipeline. A listing is two round trips (the
indexes, then the ends) and two decoded records per chat. The previous whole-history read decoded
every record to use two of them; on 20 chats of 200 messages the limited read was about 21 times
faster against the same containerized Redis. The `LLEN` gives the tail record its true index, so a
corrupt last record is named by its real position, and it runs in the same transaction so the
length and the record describe one snapshot.

A corrupt record between the ends does not take the chat list down, while `history` still fails
visibly on it, so a turn's context is never silently truncated. A corrupt record at either end
fails the listing, and a dangling index entry (an empty list) is skipped.

### 8. The chat list refreshes on summon, and no push channel exists

The list refreshes on mount, on turn completion, and on the rising edge of visibility, sharing
`useSummonEffect` with the reminder pull and the connection probe: one re-list per summon, none
while the overlay changes shape or stays hidden. A title-refresh push is not built because nothing
can produce the event: session history has one writer, `ConversationEngine` inside a turn, and the
schedule ticker writes to the task store, never to a session. So nothing changes a title or preview
while the overlay watches, except a turn the overlay itself ran, which refreshes on completion. A
background writer of session history, or a title written after its turn completes, would reopen
this. The connection indicator is derived ([ADR-0011](ADR-0011-body-v1.md) decision 8).

### 9. Brain-generated titles are written at turn end, before completion, and default off

With `CORTEX_GENERATE_TITLES` on (default `false`), the engine asks the resident cortex for a title
on a session's first turn only, from the opening exchange, after the reply's stream has released
its lease, so the call is a sequential acquire, never a re-entrant one. The title is persisted with
`SessionStore.set_title` before `TurnCompleted` is yielded, so the overlay's turn-completion
refresh already sees it and no title changes after that refresh. Generating on the list path was
rejected: listing would block on inference and compete for the GPU lease. A failure or an empty
reply is absorbed and persists nothing.

The Redis adapter stores the title as a plain string at `cortex:session:{id}:title` and reads it in
the listing's ends pipeline as `title_override`. A non-blank override wins; either way the title is
collapsed and cut again to `TITLE_MAX` at read time, so no stored title exceeds the switcher width.
The title is store state, so it survives a model swap.

`generate_title` sends `TITLE_BOUNDS` (`cortex_core/session_title.py`): `max_tokens=32`,
`thinking=False`, `trace_tokens=0`. A reasoning cortex asked without the switch spent its whole
budget thinking and returned an empty reply, at every cap tried; with the switch the same prompt
decodes about four tokens for the same title. The cap cannot change a stored title, because a reply
that reaches 32 tokens has already passed the 48 characters `clean_title` keeps. The sizing is
[ADR-0038](ADR-0038-ranked-recall.md) decision 8 and the readings are in
[ranked-recall.md](../readings/ranked-recall.md). The feature defaults off because it adds an
inference call per new session on a shared GPU.

### 10. Catalog writes are user-only RPCs, each attempted once

`RenameSession`, `DeleteSession` and `SetSessionHoisted` are unary `BrainService` writes whose only
caller is the overlay's own controls. None is a tool in any registry and none runs through the turn
engine, so no model, tool or tainted turn can reach them. That is the whole of their protection.
The confirmation rule and `SeamConfirmer` ([ADR-0013](ADR-0013-untrusted-content.md),
[ADR-0022](ADR-0022-email-write-confirmer.md)) stop a model's irreversible tool call inside a turn
and are tied to one `Converse` stream, so they do not fit a management RPC; a confirm card for one
would answer a threat the model cannot pose.

The body classifies every catalog write **not repeatable** (`SeamMethod::RenameSession`,
`DeleteSession`, `SetSessionHoisted`), so the resilient transport makes one attempt. Reads are
repeatable. A write idempotent by value still is not retried: a lost reply followed by a silent
retry could re-assert a value the user's next action reversed, which the retry loop cannot see.

Rename needs no new port method: a user label is `SessionStore.set_title`. The handler cuts the
label to `MAX_TITLE_INPUT` (200) at the wire edge, the empty string clears the override, the
display is cut again to `TITLE_MAX` on every read, and the overlay renders it as inert React text,
so a label cannot inject markup or a second line.

### 11. Deletion is a hard delete with a scope-aware memory cascade

`SessionStore.delete(session_id)` removes the `:messages` list, the `:title` string, the `:recap`
string ([ADR-0038](ADR-0038-ranked-recall.md) decision 9), the `cortex:sessions` member and the
`cortex:sessions:hoisted` member in one transactional pipeline, idempotently. A tombstone was
rejected: the reads are stateless snapshots and an unknown session already reads as an empty
history, and "forget this chat" calls for erasure.

The memory cascade stays off the turn path. `MemoryRecaller` exposes record and recall only, so no
tool or tainted turn reaches a delete. `SessionMemoryCascade(store, scope)`
(`cortex_core/memory_cascade.py`) exposes only `delete_session_memories(session_id)`, is wired by
the composition root into `DeleteSession` and never into an engine, and deletes only when the
session's write scope is the session's own (`scope == session_id`). Under the default global scope
nothing cascades. The `GLOBAL_SCOPE` check runs first, so `GLOBAL_SCOPE` is never handed to
`delete_scope`, even for a session whose id equals it. The handler deletes the session, then
cascades; either store error aborts `UNAVAILABLE`, and a retry completes the deletion.

The confirmation is overlay-local: the row's trash control swaps in a confirm and cancel pair.
Deleting the open chat first tears down its turn (denying a pending confirm and cancelling the
stream, so a reply cannot re-create the chat) and on success resets the panel to a new chat.

### 12. A hoisted chat is added to the recency listing

A chat the user hoists stays at the top of the list whatever its age, until the user lowers it. The
listing unions the recency window with the Redis set of hoisted ids, `cortex:sessions:hoisted`, read
in one pipeline and deduplicated before any fetch, so an old hoisted chat lists, a recent one lists
once, and many hoisted chats list more than `limit`. The pure `merge_hoisted`, shared by the fake
and the adapter, puts the hoisted chats first, each group newest first; the switcher, cycling and
cold-start adoption read that order.

**The name is Hoist, and its opposite is Lower.** The row's toggle (`aria-pressed`) reads
`Hoist <title>` or `Lower <title>`, acts without a confirmation and re-lists. The word says what
the row does, rising above newer chats until it is lowered, has a natural opposite, and was used
by no identifier or selectable family before. Its keys: `SessionSummary.hoisted` (field 5),
`setSessionHoisted`, the Tauri command `set_session_hoisted`, `SessionStore.set_hoisted`, the row's
`hoisted` class, the stored set and the RPC `SetSessionHoisted`, whose new method path means a body
and a brain are built together. A real store held ids under the set's first key,
`cortex:sessions:pinned`, so the adapter moves them over once, before it first uses the set.

### 13. The open-chat header shows the switcher's title

`openSession` and `adoptSession` set the header through `headerTitle(state.sessions, sessionId,
messages)`: a chat present in the loaded list takes that row's `SessionSummary.title` verbatim, and
only a chat absent from it falls back to the local `deriveTitle` of its first user message. The
switcher and the header read one snapshot, so they agree by construction for switcher opens,
cycling and adoption alike, and a generated title or a user rename reaches the header. A `title`
field on `GetSessionMessages` was not added: a second read would let a rename arriving between the
two reads make them disagree again.

### 14. One limit governs a title's length, in both trees

`TITLE_MAX` is 48 in `cortex_core/sessions.py` and in `overlay/sessionState.ts`, compared by
`scripts/crosscheck.py` ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)), and each side's
suite asserts its own literal. `_one_line` in the brain and `deriveTitle` in the overlay apply one
rule: collapse whitespace runs, and past `TITLE_MAX` cut and append one ellipsis, so an over-long
title renders at 49 characters. The two must be one number because the overlay names a chat locally
in the render that starts its first turn, and the turn-completion refresh then shows the brain's
rendering of the same message in that chat's row; the header box is also the wider of the two.
`clean_title` cuts a generated title to `TITLE_MAX` with no ellipsis, left as it is.

## Consequences

- A chat outside the loaded window derives its header locally, so it cannot show a stored rename or
  generated title. Only the reminder card's open control opens such a chat, and the switcher shows
  no row for it, so no disagreement is visible. A `title` field on `GetSessionMessagesReply` waits
  for a second caller of that kind ([180](../refinements/tasks/180-out-of-window-title.md)).
- Paging is not built. A reply encoding past the body client's 4 MiB decoding cap is the trigger,
  and a window on `GetSessionMessagesRequest` is the smaller first move
  ([184](../refinements/tasks/184-paging-cursor.md)).
- The Tauri `list_sessions` and `session_messages` commands are host-validated glue
  ([H-005](../host/tasks/005-session-read-commands.md)); the CI half is fakes on both sides.

## Alternatives rejected

- **A streaming `ListSessions` or paged history.** A recent-chat list and one history are small;
  unary snapshots match the overlay's load-then-render shape, and a cursor fits the same RPCs later.
- **The adapter derives titles, or returns raw `(session_id, last_activity)` references.** The
  first puts domain logic in an adapter; the second makes the consumer issue N+1 calls.
- **A cached first message, last message and length in the index.** A third write on `append`, not
  atomic with the other two, would leave a preview permanently wrong after a crash between them;
  the limited read of decision 7 needs no new state.
- **`google.protobuf.Timestamp`**, or **a separate `SessionCatalog` port**: the overlay converts
  the value to milliseconds at once, and listing reads state `SessionStore` already holds.

## Related

- [brain-session](../modules/brain-session.md), [brain-core](../modules/brain-core.md),
  [brain-orchestrator](../modules/brain-orchestrator.md), [`cortex_seam`](../modules/brain-seam.md),
  [body-core](../modules/body-core.md), [body-rpc](../modules/body-rpc.md),
  [body-app](../modules/body-app.md); [ADR-0008](ADR-0008-memory-v1.md) (memory scopes).
