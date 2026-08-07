// WHAT A FIELD DOES WITH A KEY THE WINDOW IS ALSO LISTENING FOR.
//
// The overlay binds five global keys on `window` (`components/Overlay.tsx`): Escape, `?`, and the
// three chords `Ctrl/Cmd+N`, `Ctrl/Cmd+K` and `Ctrl/Cmd+↑` / `Ctrl/Cmd+↓`. A field the caret is
// sitting in sees every one of them first, and the question of which it may keep was answered twice
// before this and never as a rule: `?` is a character rather than a shortcut wherever somebody is
// writing (`typing` in that file), and Escape closes the innermost thing, which an open editor is.
// The chords were left to reach the overlay, on the argument that a chord is a deliberate act.
//
// MEASURED IN CHROMIUM AT 900X900 BEFORE THIS RULE, standing in "Everything about model swaps" with
// the switcher open and "a brand new name" typed into a row's rename editor. `Ctrl+N` minted a new
// chat and closed the switcher; `Ctrl+↑` loaded "Summarize my unread email" and `Ctrl+↓` loaded
// "Reminders and recurrence", both closing it; `Ctrl+K` closed it on its own. All four discarded the
// name (the row read its old title when the list was reopened) and there is no undo anywhere for it,
// the in-progress label living in the list's own state and dying with the editor. `Ctrl+K` also left
// `document.activeElement` on `<body>`.
//
// And the field is not a bystander to two of them. Traced on a bare single-line `<input>` holding
// the same sixteen characters with the caret at offset 6 and nothing listening: `Ctrl+↑` moved it to
// 0 and `Ctrl+↓` moved it to 16, which are the field's own start-of-text and end-of-text bindings;
// `Ctrl+N` and `Ctrl+K` moved neither the value nor the selection. So the cycle keys are not spare
// inside a field, and taking them there was a collision rather than a priority.
//
// THE RULE: a chord passes through a field whose text the overlay KEEPS, and is held by a field
// whose text it would THROW AWAY. The composer keeps every keystroke under the chat it was typed
// into (`overlay/drafts.ts`), so every global key still works from where a summon lands; the rename
// editor keeps nothing, so it holds the chord until the reader has said what the name is. Enter and
// Escape both settle that in one press and both leave the caret on the pencil, so the chord is one
// further press away rather than refused. Auto-committing instead was considered and rejected: a
// half-typed name would become a store write nobody asked for, and an emptied editor commits the
// clear-the-custom-title signal, so `Ctrl+N` after a Backspace would silently wipe a title.
//
// A press held here is only `stopPropagation`, never `preventDefault`, so the field's own uses of a
// chord are untouched: select-all, copy, paste, undo, and the two caret jumps traced above all keep
// working, and `Ctrl+↑` inside the editor now does what the field says it does instead of swapping
// the conversation out from under it.

/** One press worth of the modifier state, which is all either answer below reads. Structural rather
 *  than `KeyboardEvent`, so a React synthetic event and a native one are both callable and a test
 *  can state a press as an object literal. */
export interface KeyPress {
  readonly key: string;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
}

/**
 * Whether a press is one of the overlay's chords: Ctrl on every platform, Cmd on the Mac.
 *
 * The overlay's global handler and the fields that stand in front of it read this same question, so
 * that "what counts as a chord" cannot drift into two answers that disagree about one key.
 */
export function chord(press: KeyPress): boolean {
  return press.ctrlKey || press.metaKey;
}

/**
 * What a field that would lose its text does with a press.
 *
 * `cancel`: close the editor and keep the press, which is Escape closing the innermost thing.
 * `hold`: keep the press and change nothing, which is a chord arriving at unsaved text.
 * `pass`: let it go on to the overlay, which is every other key, `?` included: that one is answered
 * one layer up by a guard asked of the element type, so passing it is what keeps the two mechanisms
 * composed rather than duplicated.
 *
 * Escape is asked first, so a modified Escape still cancels. Nothing binds Ctrl+Escape here, and the
 * reader who presses it is reaching for the way out of the editor.
 */
export type FieldKey = "cancel" | "hold" | "pass";

export function fieldKey(press: KeyPress): FieldKey {
  if (press.key === "Escape") {
    return "cancel";
  }
  return chord(press) ? "hold" : "pass";
}
