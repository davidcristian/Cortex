# Session deletion, rename, and pinning

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

Write operations on the catalog, a later *gated* surface
(Slice 6.5 gate + Slice 8.8 Confirmer), out of scope for this read-only slice.
**Rename landed 2026-07-16 ([ADR-0021 rename addendum](../../adr/ADR-0021-session-read-seam.md)); pin
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

## Trail

- 2026-07-16: The entry was read as three changes rather than one and the area count went from
  4 to 5. Rename landed end to end as a gated user-only write reusing the `set_title` the
  titles work built, so no new port method, while pin and delete opened as their own
  entries. The index names the "gated ... Confirmer" framing the second correction of a
  Confirmer premise made by reading against the code that day, the first of the two being the
  tainted-turn confirm decline. The index also states why neither of the other two verbs could
  ride the rename: pin reshapes the tuned read path, the open question being whether a pinned chat
  escapes the recency window, and delete could not then cascade to memory, `MemoryStore` having had
  no delete verb until `delete_scope` landed the same day.
