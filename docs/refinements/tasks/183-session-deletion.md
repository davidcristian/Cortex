# Session deletion

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

Destructive and irreversible: a session delete would remove the transcript
and catalog entry (a `SessionStore.delete` verb, likely a tombstone rather than a hard `DEL` so an
in-flight read fails cleanly). The memory-cascade half is **no longer blocked on a missing verb**:
it landed 2026-07-16 as `MemoryStore.delete_scope(scope)` ([memory.md](../index.md#memory),
[ADR-0008](../../adr/ADR-0008-memory-v1.md)), so a delete can cascade to a session's derived memories
by their scope. It cascades honestly **only under session scoping** (`SessionMemoryScope`, where
`scope == session_id`); under the default global scope a session's memories are the shared
cross-conversation space, so there is nothing session-private to cascade and the cascade must
**not** pass `GLOBAL_SCOPE`. The entry still needs an **overlay-local** confirm ("are you sure"),
since the `SeamConfirmer` gates in-turn tool calls, not a unary management RPC (see the rename
finding above). Still deferred: design the `SessionStore.delete` verb, the scope-aware cascade, and
the confirm surface together.
**Landed 2026-07-16 ([ADR-0021 delete addendum](../../adr/ADR-0021-session-read-seam.md)), and the
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

## Trail

- 2026-07-16: Deletion landed end to end and opened nothing behind it, taking the area count
  from 5 to 4. All three halves the entry bundled shipped together: the `SessionStore.delete`
  verb, the scope-aware memory cascade, and the overlay-local confirm.
