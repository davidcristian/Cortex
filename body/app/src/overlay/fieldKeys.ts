// What a field does with a key the window is also listening for.
//
// The overlay binds five global keys on `window` (`components/Overlay.tsx`): Escape, `?`, and the
// three chords `Ctrl/Cmd+N`, `Ctrl/Cmd+K` and `Ctrl/Cmd+↑` / `Ctrl/Cmd+↓`. A field the caret is
// sitting in sees every one of them first. `?` is a character rather than a shortcut wherever
// somebody is writing (`typing` in that file), Escape closes the innermost thing, which an open
// editor is, and the chords were left to reach the overlay on the argument that a chord is a
// deliberate act.
//
// The rule that replaced that: a chord passes through a field whose text the overlay keeps, and is
// held by a field whose text it would throw away. The composer keeps every keystroke under the chat
// it was typed into (`overlay/drafts.ts`), so every global key still works from where a summon
// lands; the rename editor keeps nothing, so it holds the chord until the reader has said what the
// name is. Enter and Escape both settle that in one press and both leave the caret on the pencil,
// so the chord is one further press away rather than refused. The ADR-0035 addendum of 2026-08-07
// carries the traces behind all of that, including the two cycle keys turning out to be the field's
// own start-of-text and end-of-text bindings, and the two alternatives it rejected.
//
// A press held here is only `stopPropagation`, never `preventDefault`, so the field's own uses of a
// chord are untouched: select-all, copy, paste, undo, and the caret jumps `Ctrl+↑` and `Ctrl+↓` make
// inside a field all keep working.

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
