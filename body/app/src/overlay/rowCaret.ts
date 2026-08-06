// Where the caret goes when a list reshapes under the hand. A row that changes shape hands the
// caret to the control its new shape puts in place of the one that left; a row that leaves hands
// it to the row that takes its place; and a list with nothing left hands it to its anchor.

import { type RefObject, useCallback, useLayoutEffect, useRef, useState } from "react";

/** The attribute a control has so a list can send the caret to it by name. */
const CARET_ATTRIBUTE = "data-caret";

/** The name of one control in one row, as the rows write it and the list asks for it. A null id
 *  passes through, which is what `heir` answers for a list with nothing left, so the call sites
 *  stay one expression. */
export function caretKey(role: string, id: string | null): string | null {
  return id === null ? null : `${role}:${id}`;
}

/** The row that takes a departing row's place: the one below it, else the one above it, else none
 *  at all. Below before above, because the row below is the one that moves into the gap under a
 *  pointer the reader has not moved. */
export function heir(keys: readonly string[], gone: string): string | null {
  const at = keys.indexOf(gone);
  if (at === -1) {
    return null;
  }
  return keys[at + 1] ?? keys[at - 1] ?? null;
}

/** Give a list the caret to hand out, and return the way to hand it. The returned function names
 *  the control that should hold the caret once the change is on screen, or `null` for "no row can
 *  take it". Named by key, because that control usually does not exist yet when it is asked for. */
export function useRowCaret(
  list: RefObject<HTMLElement | null>,
  anchor: RefObject<HTMLElement | null>,
): (key: string | null) => void {
  // Held as an object rather than a bare key, so that "nothing was asked for" and "the anchor was
  // asked for" stay two states: both are a null key otherwise, and only the second moves the caret.
  const wanted = useRef<{ readonly key: string | null } | null>(null);
  // Counted, so that asking is what schedules the move rather than the caller's own state change
  // happening to.
  const [handoff, setHandoff] = useState(0);
  useLayoutEffect(() => {
    const want = wanted.current;
    if (want === null) {
      // Nothing has been asked for. A stream re-rendering the chat around an untouched list never
      // reaches this, so it cannot take the caret off whatever the reader moved it to.
      return;
    }
    wanted.current = null;
    const controls = list.current?.querySelectorAll<HTMLElement>(`[${CARET_ATTRIBUTE}]`) ?? [];
    // Matched on the dataset rather than folded into the selector above, so an id with a quote in
    // it is a key that misses rather than a selector that throws.
    const found = [...controls].find((control) => control.dataset.caret === want.key);
    if (found === undefined) {
      // Without scrolling, here and below: the panel clips its overflow, so bringing a newly
      // focused element into view moves everything in it.
      anchor.current?.focus({ preventScroll: true });
      return;
    }
    found.focus({ preventScroll: true });
    if (found instanceof HTMLInputElement) {
      // The one field this reaches is the rename editor, which opens holding the title it is about
      // to replace. Selecting it makes typing replace the name and one Backspace clear the custom
      // title, where bare focus puts the caret at the end of the existing name.
      found.select();
    }
  }, [handoff, list, anchor]);
  return useCallback((key: string | null) => {
    wanted.current = { key };
    setHandoff((asked) => asked + 1);
  }, []);
}
