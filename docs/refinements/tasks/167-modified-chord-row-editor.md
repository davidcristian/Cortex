# A keyboard shortcut reaching the overlay from a row's editor

**Status:** done 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

With the caret now arriving in the rename editor, Escape and `?` were handled there but `Ctrl+N`,
`Ctrl+K` and the cycle keys were not. Measured at 900x900 with "a brand new name" typed into a row's
editor, all four fired the overlay shortcut and discarded the edit, and nothing holds an undo for
it. `Ctrl+K` also left focus on `<body>`.

Two of the four keys belong to the field. Traced on a bare single-line `<input>` with nothing
listening, `Ctrl+↑` moved the caret to the start of the text and `Ctrl+↓` to the end, while `Ctrl+N`
and `Ctrl+K` moved neither the value nor the selection. So half of this was the overlay taking keys
the field already uses.

The rule that shipped is about the text, not the key: a shortcut passes through a field whose text
the overlay keeps, and is held by a field whose text it would discard. The composer keeps every
keystroke under the chat it was typed into, so every global key still works from there. The rename
editor keeps nothing, so it holds the shortcut until the reader has said what the name is, which
costs one press of Enter or Escape. Firing the shortcut instead costs the whole name with no undo.
Auto-committing the name first was rejected: it makes a store write nobody asked for, and an emptied
editor sends the signal that clears a custom title, so `Ctrl+N` after a Backspace would erase one.
The delete confirm still passes shortcuts through, since it holds no text to lose.

Cost: `overlay/fieldKeys.ts`, a 76-line pure module holding `chord` and a `fieldKey` that returns
`cancel`, `hold` or `pass`, plus the row's editor handler rewritten over it. The overlay's own `mod`
now calls the same `chord`, so the two sides cannot disagree about what counts as a shortcut. The
entry's stated cost was wrong: a guard in `Overlay.tsx` would have to name the editor by selector
and spare the composer by name.

Afterwards all four shortcuts leave the editor open with its text, its caret and the switcher
unchanged. Settle with Enter and the same press does what it says. Inside the editor `Ctrl+↑` and
`Ctrl+↓` now move the caret, which they could not do before, because the hold is `stopPropagation`
and never `preventDefault`.

One measuring note: the first attempt to measure `Ctrl+↑` reported nothing happening, which was not
the editor but `cycleTarget` having nowhere to go from a fresh unsaved chat
(`overlay/sessionState.ts`).

## History

- 2026-08-06: Opened by the caret rule above, which made the rename editor somewhere the caret
  arrives rather than somewhere it is clicked into.
- 2026-08-07: Closed, and opened two entries behind it: the closing-list caret and the silence of a
  held shortcut. It was filed as a decision made without a measurement, and the measurement changed
  the answer.
