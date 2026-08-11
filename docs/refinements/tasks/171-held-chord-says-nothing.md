# A held chord saying nothing about being held

**Status:** declined 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-07 by the chord entry above, whose
answer is deliberately silent: the press is stopped, the editor stays exactly as it was, and the
overlay makes no sound about why the key a reader just pressed did nothing. For a sighted reader
the state on screen is the whole of the explanation, an open editor with the caret in it and the
name selected, which is why it shipped this way and why the alternative was not bundled into a
slice that was already deciding a rule. For a reader on a screen reader it is thinner: focus is
on an input labelled "New chat name", `Ctrl+N` produces no event, no focus move and no announced
change, so nothing distinguishes a chord the editor held from a chord the application ignored.
The shapes are the overlay's existing live region saying the editor is waiting, a `role="status"`
line the editor owns, or nothing at all on the argument that a key doing nothing needs no
narration. This wants the same measurement in a real reader that the silent-shrink entry below
wants, and the two should probably be picked up together, since both are about what the region's
contract is allowed to carry beyond "the conversation that arrived". Nothing blocks it.
- **SHARPENED 2026-08-07 by the silent-shrink entry below, which settled the shared question and
  did NOT bundle this** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The contract
  this was waiting on is decided: the region may carry more than an arrival, and everything it may
  say is built in `overlay/notice.ts`, so the first shape is no longer blocked on a decision. Three
  measured reasons it stays its own entry rather than riding along.
  **What a shrink destroys, a held chord leaves standing**, and that is the test the shrink's own
  close chose. Measured at 900x900 with `a brand new name` typed into a row's editor: `Ctrl+N`
  produced zero live-region mutations, and both before and after the press the focused element was
  the `input` labelled "New chat name" holding that exact value. Nothing was lost, so the reader
  can re-read it; a deleted row is out of the accessibility tree and cannot be re-read at all.
  **It is a different seam.** Every sentence the shrink close added was already at a reducer arm
  (`sessionState.deleteSession`, `overlayState`'s `reminderDismissed`), so it plumbed nothing. The
  hold is decided in `SessionRow`'s keydown over `SessionList`'s own state and nothing in that path
  touches the reducer, so publishing from it wants a callback through `Panel`, `ChatView`,
  `SessionList` and `SessionRow`, plus an `OverlayController` member and an `Action` variant. That
  is the entry's real cost and it was never stated.
  **And it has a policy question the shrink did not.** A chord fires per keydown and keydown
  repeats while a key is held, so this is the one sentence in the region a reader can raise dozens
  of times without moving, and the count key makes every one of them a fresh announcement by
  design. A guard (`event.repeat`, or a latch per editor) is part of the shape rather than a
  detail, which is a fourth thing to decide and not a line to add.
  A shape it can now also weigh, which neither doc named: say it **on the editor itself** rather
  than in the region, as an `aria-describedby` line the input carries while a chord is pending, so
  the explanation sits with the thing the reader is standing in and is re-readable instead of
  spoken once. Still open, still blocking nothing.
- **DECLINED 2026-08-07, all four shapes, and the deciding fact is not the one either doc was
  arguing about** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Measured first, in
  headless Chromium at 900x900 against the demo bridge, standing in the editor on "Everything
  about model swaps" with `a brand new name` typed and the caret parked at offset 6: the
  accessibility node of whatever holds the caret, the value and the selection before and after
  each press, a `MutationObserver` on every live-region-shaped node, and a `window` keydown
  listener recording whether the press got past the editor.
  **The entry's own reading reproduced exactly.** The focused node reads `textbox`, named
  "New chat name", valued `a brand new name`, with no description and no `aria-describedby`,
  identically before and after `Ctrl+N`, `Ctrl+K`, `Ctrl+↑` and `Ctrl+↓`; all four raise zero
  mutations in any live region and leave the editor open. **The instrument is not why it reads
  clean**, which a decline has to show rather than assume: the same observer catches
  `Chat deleted. 2 chats left.` on a delete, and the same window listener records `Control`, `n`
  for `Ctrl+N` pressed in the composer and over an open delete confirm, the two surfaces that pass
  chords by design.
  **What neither doc had is that the hold is not four keys. It is every chord there is**, which is
  this chain's undercount lesson arriving for the fifth entry running and in its sharpest form,
  because here the undercount is what decides the entry. `fieldKey` asks whether a press is
  modified and nothing else, deliberately, so that "what counts as a chord" has one definition on
  both sides of the window listener. Nine presses measured through that one branch, every one of
  them stopped from reaching the window: `Ctrl+N` and `Ctrl+K` did nothing at all, `Ctrl+↑` and
  `Ctrl+↓` moved the caret 6 to 0 and 6 to 16, `Ctrl+A` selected all sixteen characters, `Ctrl+←`
  and `Ctrl+→` moved it 6 to 2 and 6 to 7, `Ctrl+Backspace` deleted a word (`a brand new name` to
  `a d new name`), and `Ctrl+Z` undid the whole edit back to `Everything about model swaps`.
  **Seven of the nine did something anyway, two of them changing the text.**
  **So the region is refused because the sentence would be false at most of its doors.** Raised at
  the `hold` branch it fires on all nine, so a reader who pressed `Ctrl+Z` and watched their name
  come back would be told the editor is waiting. Making it true means teaching `fieldKeys.ts`
  which chords the overlay binds, which is exactly the coupling the hold rule removed by deciding
  about the text rather than about the key, and which goes stale the day a fifth chord is bound.
  **The `role="status"` line is refused** for that and for the region-inside-a-section defect the
  shrink close already measured one surface over: the editor is unmounted by Enter and by Escape,
  so a region inside it leaves in the commit after the sentence it would carry, and it would be a
  second region competing for the reader's speech queue besides. **The description is refused**
  because an accurate one is the key table in the markup: "shortcuts wait until the name is saved"
  misdescribes a field where seven of nine chords do not wait, and the accurate version enumerates
  the bound three and is spoken on every rename to serve a press most readers never make.
  **And the silence passes the test the region's own contract sets.** The shrink close earned its
  place by what a gesture DESTROYS, a deleted row being out of the tree and unre-readable. A held
  chord destroys nothing, measured to the attribute, so everything a reader might want is still
  there to be read; the editor announces itself when it opens (the tree reading `textbox` named
  "New chat name", valued with the title it stands for, all twenty eight characters selected) and
  again when it closes, measured this session: Escape lands the caret on
  `button[Rename Everything about model swaps]` and Enter on `button[Rename a brand new name]`, so
  the way out reads back the name that was settled. A key that did nothing, in a field that is
  exactly as it was, is not news.
  **The repeat policy is left unanswered rather than answered**, a rule that raises no sentence
  needing no latch. It was measured anyway, since the next thing that speaks per keydown inherits
  it: thirty `keydown` events carrying `repeat: true` dispatched at the editor were all seen by
  its handler, twenty nine of them carrying `repeat: true`, nothing in the path filtering one. CDP
  does not synthesise platform autorepeat, so what is measured is the absent guard rather than the
  repeat itself.
  Nothing opened behind it. What only a real reader can settle is already filed at
  [host/overlay-screen-reader.md](../../host/index.md#overlay-screen-reader), whose table has carried this
  press as "nothing, deliberately" since the sitting was written; if a reader there cannot tell a
  held chord from a dead application, that finding reopens this as a rule about the overlay's
  whole key table rather than about one field.

## Trail

- 2026-08-07: Opened by the chord entry above, whose answer is deliberately silent.
- 2026-08-07: Read alongside the silent-shrink entry when that one closed and deliberately not
  bundled with it, which in this area is the unusual outcome. The shared question closes for both,
  the region being allowed to carry more than an arrival, and what keeps this one separate is
  measured rather than tidy. It was sharpened with those reasons and with a fourth shape neither doc
  had named.
- 2026-08-07: Declined, all four shapes, on the measurement that the rename editor holds every chord
  there is and that seven of the nine measured do something in the field anyway. Nothing opened
  behind it, and what only a real reader can settle was already filed at the overlay screen-reader
  sitting.
