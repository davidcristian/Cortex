# Write operations on the session catalog

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

Deleting, renaming and reordering a chat were all out of scope for the read-only slice. Rename
shipped on 2026-07-16; the other two opened as the two entries below.

The entry expected these to go through the `SeamConfirmer`, which is wrong for a management RPC.
That confirmer (ADR-0022) checks a possibly-jailbroken model's tool call inside a turn: one per
`Converse` stream, a mid-turn card, tainted turns denied outright. A rename is triggered by the user
in the overlay, out of band, and its handler is no tool in any registry and never runs through the
turn engine, so no model, tool or tainted turn can reach it. What protects it instead is that only
the user can reach it: `RenameSession` is a distinct `BrainService` method served off the store,
whose only caller is the overlay's `renameSession` bridge.

Rename needed no new port method either, since a user rename is `SessionStore.set_title`, the write
the brain-generated titles built. The slice added only the RPC, a bounded handler (`session_rpc`),
the non-repeatable body transport call, and the switcher's rename control.

The three operations were never one change: rename reuses an existing write and is reversible, while
reordering reshapes the read path and deleting could not yet say accurately what it destroys.

## History

- 2026-07-16: Read as three changes rather than one. Rename shipped end to end, reusing
  `set_title`, while the other two opened as their own entries. The expectation that a confirmer
  would be involved was the second such premise corrected by reading the code that day. Neither
  other operation could come with the rename: reordering reshapes the tuned read path, with the open
  question being whether a chat kept at the top escapes the recency window, and deleting could not
  then cascade to memory, since `MemoryStore` had no delete until `delete_scope` shipped the same
  day.
