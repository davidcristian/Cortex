# Session deletion

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

Deleting a session removes the transcript and the catalog entry, is irreversible, and had to be
designed together with its memory cascade and its confirm surface. All three shipped together.

`SessionStore.delete(session_id)` is a hard delete, not the tombstone the entry guessed. The reads
are stateless snapshots and an unknown session already reads as an empty `history`, so a deleted
chat degrades cleanly with no in-flight id to protect, and a privacy-motivated "forget this chat"
wants real erasure. The Redis adapter drops all three keys a chat can have, the `:messages` list,
the `:title` string and the `cortex:sessions` member, in one transactional pipeline, and is
idempotent.

The cascade is not on the turn-facing `MemoryRecaller`, which would put a forget verb on the turn,
but on a separate trusted `SessionMemoryCascade(store, scope)` the orchestrator wires into
`DeleteSession` only. It targets `write_scope(session_id)` and runs only when that scope is the
session's own private space (`scope == session_id`); under the default global scope a session's
memories are the shared cross-conversation space, so there is nothing private to remove. The
`GLOBAL_SCOPE` guard is checked first, so `GLOBAL_SCOPE` can never reach `delete_scope` even for a
session whose id equals it.

The confirm is in the overlay, since the `SeamConfirmer` checks in-turn tool calls rather than a
unary management RPC: the switcher row's trash swaps in an inline "Delete this chat?" pair, and
`onDelete` fires only on the second, explicit click. `DeleteSession` has the same structural
user-only reachability as rename, and its `SeamMethod` is classified not repeatable, so the body
makes exactly one attempt at a destructive call.

The overlay also handles the open-chat case: deleting the open chat tears down its in-flight turn,
so a streaming reply cannot recreate the chat with a post-delete `append`, and falls back to a fresh
chat.

Checked live against real Redis and pgvector: every key gone, the recency member gone,
session-scoped memories gone, a global-scoped memory untouched.

## History

- 2026-07-16: Closed end to end, opening nothing behind it. The memory cascade had stopped being
  blocked earlier the same day, when `MemoryStore.delete_scope(scope)` shipped
  ([ADR-0008](../../adr/ADR-0008-memory-v1.md)).
