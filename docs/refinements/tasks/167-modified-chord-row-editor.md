# A modified chord reaching the overlay from a row's editor

**Status:** landed 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-06 by the
entry above, which made the rename editor a place the caret lands rather than a place it is clicked
into. Escape and `?` are answered there now; `Ctrl+N`, `Ctrl+K` and the cycle keys are not, so
pressing `Ctrl+N` mid rename mints a new chat, closes the switcher and discards the edit. That is
arguably correct, a chord being a deliberate act rather than a character somebody is typing, and it
is the reason it was not changed with the other two; it is recorded because it was noticed and
decided rather than measured, and because the same question will be asked of the next field the
overlay grows. Neither behaviour is measured today. Cost is a few lines in `Overlay.tsx` if the
answer is that an open editor swallows chords too, or nothing at all if the answer is that it does
not. Nothing blocks it.
- **LANDED 2026-08-07 as a rule about what a field would LOSE rather than about what a chord IS**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). **The entry's account of the code
  reproduced, and it was measured before anything was touched.** Chromium at 900x900 against the
  demo bridge, standing in "Everything about model swaps" with the switcher open and "a brand new
  name" typed into the third row's editor: `Ctrl+N` minted a chat and closed the switcher, `Ctrl+↑`
  loaded "Summarize my unread email", `Ctrl+↓` loaded "Reminders and recurrence", and `Ctrl+K`
  closed the list on its own. All four discarded the name, every row reading its old title when the
  list was reopened, and nothing anywhere holds an undo for it. Escape and `?` behaved as the entry
  said: Escape cancelled to the pencil with the panel still up, and "why?" left `why?` in the field
  with no console over it.
  **Three things the entry did not have.** `Ctrl+K` also left `document.activeElement` on
  `<body>`, which is the landing the caret rule shipped the day before to abolish; the other three
  hand the caret to the composer, which is the arrival rule doing its job. **Two of the four keys
  are the field's own**: traced on a bare single-line `<input>` holding the same sixteen characters
  with the caret at offset 6 and nothing listening, `Ctrl+↑` moved it to 0 and `Ctrl+↓` moved it to
  16, those being start of text and end of text, while `Ctrl+N` and `Ctrl+K` moved neither the
  value nor the selection. So half of this was a collision rather than a priority: the overlay was
  taking keys the field already uses. And **the first attempt to measure `Ctrl+↑` reported a
  no-op**, which is not the editor answering but `cycleTarget` having nowhere to go from a fresh
  unsaved chat (`overlay/sessionState.ts`); it is recorded because a careless run reads that as
  the entry failing to reproduce.
  **The verdict: an open editor HOLDS a chord, and the rule is about the text and not about the
  key.** A chord passes through a field whose text the overlay keeps and is held by a field whose
  text it would throw away. The composer keeps every keystroke under the chat it was typed into,
  so every global key still works from where a summon lands, which is where these keys are pressed
  from; the rename editor keeps nothing, so it holds the chord until the reader has said what the
  name is. That costs one press, Enter or Escape, both already bound and both leaving the caret on
  the pencil with the chord one further press away. Firing the chord instead costs the whole name
  with no undo, which is a different class of harm from a chord waiting, and the overlay had
  already ruled a day earlier that a half-typed sentence is work rather than something a swap may
  discard. Auto-committing the name first was considered and rejected: it makes a store write
  nobody asked for, and an emptied editor commits the clear-the-custom-title signal, so `Ctrl+N`
  after a Backspace would wipe a title. The delete confirm is deliberately left passing
  chords, holding no text to lose (measured: `Ctrl+N` over an open question minted the chat, closed
  the switcher and deleted nothing).
  **What it cost**: `overlay/fieldKeys.ts`, a 76-line pure module holding `chord` and a `fieldKey`
  that answers `cancel`, `hold` or `pass`, plus the row's editor handler rewritten over it. The
  overlay's own `mod` now asks that same `chord`, so the two sides of the seam cannot drift about
  which press is one. **The entry's stated cost was wrong**: a guard in `Overlay.tsx` would have to
  name the editor by selector, which is the shape the `?` guard's own doc rejects, and would have
  to spare the composer by name, which is the case that must keep working.
  **After, measured the same way.** All four chords leave the editor open with `a brand new name`
  in it, the caret in it, the switcher expanded and the title unmoved. Settle with Enter and the
  same press then does what it says: `Ctrl+N` gives "New chat", `Ctrl+K` closes the list, `Ctrl+↑`
  loads "Summarize my unread email" and `Ctrl+↓` loads the renamed row. Inside the editor `Ctrl+↑`
  and `Ctrl+↓` now move the caret 6 to 0 and 6 to 16, which they could not do at all before, the
  hold being `stopPropagation` and never `preventDefault`. `?` is still a character there and
  Escape still cancels to the pencil. One thing left open behind it, below.

## Trail

- 2026-08-06: Opened by the caret rule above, which made the rename editor somewhere the caret lands
  rather than somewhere it is clicked into.
- 2026-08-07: Landed, taking twelve to eleven, and opened two behind it, the closing-list caret and
  the silence of a held chord, which took eleven to thirteen. Reading the area's entries against the
  header that counts them the same day then turned up a fourteenth no count had ever named, the
  liquid edge's backdrop blur. This entry was filed as a decision made without a measurement, and
  the measurement changed the answer; its stated cost was wrong in this file's usual direction.
