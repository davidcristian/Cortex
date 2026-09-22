# Keeping a chat at the top of the list has no designed name

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-22

The overlay lets the user keep a chat at the top of the chat list whatever its last message. Its
only name is a word the documents may not use, so every sentence about it says "keeps a chat at the
top of the list", which is a description and not a name.

The code still uses that word throughout: `pinned` on `SessionSummary` in
`body/app/src/bridge/types.ts`, `setSessionPinned` on the bridge and in
`body/app/src/overlay/useSessionCatalog.ts`, the `set_session_pinned` Tauri command, the
`SetSessionPinned` RPC in `proto/body.proto`, `SessionStore.set_pinned` in the brain, the Redis set
`cortex:sessions:pinned`, the row's `pinned` CSS class, its `PinIcon` and its labels `Pin <title>`
and `Unpin <title>`. The naming rule in AGENTS.md asks for a designed word here, with no collision
with the mark's Mull, Muse, Hunch and Tangent or the window's Still, Lucid, Reverie and Trance.

**Proposed names**, for the maintainer to pick. Each was checked against the code, the stylesheet
and the documents on 2026-09-22.

- **Hoist**, recommended. The toggle is Hoist and Lower, the state is hoisted, and the top group is
  the hoisted chats. It says what the row does: it rises above newer chats and stays there until it
  is lowered, the way a flag stays up. It has a natural opposite, as the old word did, and no
  collision: `hoist` appears in no source file, and `lower` only as an ordinary adjective. The icon
  becomes an arrow rising to a bar. Keys: `hoisted`, `setSessionHoisted`, `set_session_hoisted`,
  `SetSessionHoisted`, `SessionStore.set_hoisted`, `cortex:sessions:hoisted`.
- **Sticky**. The toggle is Stick and Unstick. Forums use this word for exactly this behavior, a
  thread kept at the top whatever its activity, so a user already knows it, and the current icon
  can stay. `sticky` appears nowhere in the code or the stylesheet today, though a reader of the
  stylesheet knows it as `position: sticky`.
- **Keep**. The toggle is Keep and Release. It uses no figure at all. The cost is that `keep` and
  `kept` are ordinary words used 30 times in the overlay's code, so a search for the feature
  finds noise, and a kept chat reads as one protected from deletion, next to the delete control on
  the same row.

Rejected: Anchor, because the overlay already uses `anchor` 97 times for where a caret or popover is
placed; Dwell, because the brain's spill note measures a `dwell` duration; Hold, because the panel's
edge memory is `held`; Star, because it means a favorite, not an order.

**What would close it.** The maintainer's pick, then the rename across the contract, the brain's
session store, the overlay and the documents. The stored set outlives a reinstall, so the rename
moves the members of `cortex:sessions:pinned` into the new key once, or the store reads both for a
release.

## History

- 2026-09-19: opened when the documents around this feature were found to have no name for it.
- 2026-09-22: the panel's edge no longer uses the word, renamed with the identifiers under
  ADR-0040 decision 15. The mark's still orbit, `pinned()` in `body/app/src/mark/marks.ts`, does,
  and is an identifier for [R-705](705-names-inside-files-still-use-banned-words.md) rather than
  this feature. Three names are proposed above; the pick is the maintainer's.
