# Keeping a chat at the top of the list has no designed name

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-19

The overlay lets the user keep a chat at the top of the chat list whatever its last message. Its
only name is a word the documents may not use, so every sentence about it says "keeps a chat at the
top of the list", which is a description and not a name.

The code is unchanged and uses that word throughout: `pinned` on `SessionSummary` in
`body/app/src/bridge/types.ts`, `setSessionPinned` on the bridge and in
`body/app/src/overlay/useSessionCatalog.ts`, the `set_session_pinned` Tauri command, the
`SetSessionPinned` RPC in `proto/body.proto`, and `SessionStore.set_pinned` in the brain. The
naming rule in AGENTS.md asks for a designed word here: one word, from a family whose structure
means something, with no collision with the mark's Mull, Muse, Hunch and Tangent or the window's
Still, Lucid, Reverie and Trance. The same word is also used for two unrelated things in the
overlay, the panel edge in `panelGeometry.ts` and the still orbit in `marks.ts`, which a designed
name would separate.

**What would close it.** A recommended name with two or three alternatives, then the rename across
the contract, the brain's session store, the overlay and the documents. The wire name is part of
the contract and the stored value outlives a reinstall, so every side changes together or none
does.

## History

- 2026-09-19: opened when the documents around this feature were found to have no name for it.
