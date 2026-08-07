// What a field does with a key the window is also listening for. A chord passes through a field
// whose text the overlay keeps, and is held by a field whose text it would throw away.

/** One press worth of the modifier state, which is all either answer below reads. */
export interface KeyPress {
  readonly key: string;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
}

/** Whether a press is one of the overlay's chords: Ctrl on every platform, Cmd on the Mac. The
 *  overlay's global handler and the fields in front of it read this same question, so they cannot
 *  disagree about one key. */
export function chord(press: KeyPress): boolean {
  return press.ctrlKey || press.metaKey;
}

/** What a field that would lose its text does with a press. `cancel` closes the editor and keeps
 *  the press, `hold` keeps the press and changes nothing, and `pass` lets it reach the overlay. */
export type FieldKey = "cancel" | "hold" | "pass";

/** Escape is asked first, so a modified Escape still cancels: nothing binds Ctrl+Escape, and the
 *  reader pressing it wants out of the editor. A press held here is only `stopPropagation`, so the
 *  field's own uses of a chord, such as select-all and paste, keep working. */
export function fieldKey(press: KeyPress): FieldKey {
  if (press.key === "Escape") {
    return "cancel";
  }
  return chord(press) ? "hold" : "pass";
}
