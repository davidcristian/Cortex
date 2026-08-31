import { type RefObject, useCallback, useLayoutEffect, useRef, useState } from "react";

// Where the caret goes when a list reshapes under the hand.
//
// The caret follows the conversation whenever one arrives (`OverlayState.arrival`, `Composer`).
// That rule answers every gesture that replaces the chat and nothing else, and the overlay's two
// lists spend most of their gestures not replacing it: a rename opens an editor over a row, a
// confirm opens over another, each of them closes again, a row is deleted, a reminder is acked.
// Every one of those takes the pressed control off the page, and measured at 900x900 every one of
// them left `document.activeElement` on `<body>`, outside the panel and one Tab from the top of the
// whole document, which is further from the list than the reader was before they touched it.
//
// So a list keeps the caret. The rule, in one sentence: a row that changes shape hands the caret
// to the control its new shape puts in the place of the one that left; a row that leaves hands it to
// the same control in the row that inherits its place; and a list with no row left to give it hands
// it to its anchor, the one control outside itself that the reader is left standing on.
//
// At the commit rather than at the end of the roll, which is the call the arrival rule made and
// which has a second reason of its own here. The control the caret is being sent to has been on
// screen all along: the heir of a deleted row never left, and a row changing shape mounts its new
// controls in the very commit the old ones go. So there is nothing to wait for, and waiting would
// mean the caret sitting somewhere for the length of a 300ms roll. Measured at HEAD, waiting means
// two different somewheres, which is the other half of the argument: a switcher row is `inert` and
// unmounted the moment its chat leaves `sessions`, so the caret is already on `<body>` and would
// stay there for the roll, while an acked reminder's button survives its whole roll, so the caret
// would ride an element animating to nothing. One clock answers both, and it is the earliest one.

/** The attribute a control carries so a list can send the caret to it by name. */
const CARET_ATTRIBUTE = "data-caret";

/**
 * The name of one control in one row, as the rows write it and the list asks for it.
 *
 * Passing through a null id (which is what `heir` answers when a list has nothing left) keeps the
 * call sites one expression: the list asks for the heir's control and gets "no control", which is
 * the anchor's cue.
 */
export function caretKey(role: string, id: string | null): string | null {
  return id === null ? null : `${role}:${id}`;
}

/**
 * The row that inherits a departing row's place: the one below it, else the one above it, else
 * none at all.
 *
 * Below before above, because the row below is the one that literally moves into the gap and is
 * therefore the row the reader's eye is about to find under the pointer they have not moved. Above
 * is the answer only for the last row, which has nothing under it. A key that is not in the list
 * has no place to leave, so it has no heir either; that is not reachable from the two lists here,
 * both of which ask about a row they are rendering, and it is the answer that stays true if one
 * ever asks about a row that has already gone.
 */
export function heir(keys: readonly string[], gone: string): string | null {
  const at = keys.indexOf(gone);
  if (at === -1) {
    return null;
  }
  return keys[at + 1] ?? keys[at - 1] ?? null;
}

/**
 * Give a list the caret to hand out, and answer the way to hand it.
 *
 * The returned function is called from the gesture's own handler, beside the state it changes, and
 * names the control that should hold the caret once that change is on screen: a key that some row
 * carries, or `null` for "no row can take it". The move itself happens in the layout effect below,
 * in the commit that reshapes the list and before the browser paints it.
 *
 * Named by key rather than held as a ref because the control being aimed at usually does not exist
 * yet when the gesture fires: the editor a rename opens, the confirm a delete opens, and the row a
 * pencil comes back into are all mounted by the very render the gesture triggers. The rows write
 * their own names (`caretKey`) and the list looks one up, which is `useTravel`'s arrangement, one
 * container ref and a selector, applied to focus instead of to position.
 *
 * `anchor` is where the caret goes when no row claims the key, which is a list that has just
 * emptied. It is a control the list does not own, since the whole point is that the list has
 * nothing left, so it is passed in by whoever renders both.
 */
export function useRowCaret(
  list: RefObject<HTMLElement | null>,
  anchor: RefObject<HTMLElement | null>,
): (key: string | null) => void {
  // Held as one object rather than as a bare key, so that "nothing was asked for" and "the anchor
  // was asked for" stay two different states: both of them are a null key otherwise, and the second
  // has to move the caret while the first must not touch it.
  const wanted = useRef<{ readonly key: string | null } | null>(null);
  // And counted, so that asking is what schedules the move rather than the caller's own state
  // change happening to. Every gesture that calls this does change what its list renders, so the
  // render would come anyway and this costs no commit (one handler is one batch); what it buys is a
  // hook that does not depend on its callers happening to re-render.
  const [handoff, setHandoff] = useState(0);
  useLayoutEffect(() => {
    const want = wanted.current;
    if (want === null) {
      // The mount, where nothing has been asked for yet. Every render in between is not even
      // reached: a stream re-rendering the chat around an untouched list leaves `handoff` alone,
      // so this never runs and cannot take the caret off whatever the reader moved it to.
      return;
    }
    wanted.current = null;
    const controls = list.current?.querySelectorAll<HTMLElement>(`[${CARET_ATTRIBUTE}]`) ?? [];
    // Matched on the dataset rather than folded into the selector above, so an id with a quote in
    // it is a key that misses rather than a selector that throws. The ids are the brain's, and this
    // never has to know what a session id may contain.
    const found = [...controls].find((control) => control.dataset.caret === want.key);
    if (found === undefined) {
      // Without scrolling anything, here and below, for the reason the composer's own focus gives
      // at length: the panel clips its overflow, which makes it a scroll box the user can never
      // scroll and the engine can, and bringing a newly focused element into view is exactly when
      // it does.
      anchor.current?.focus({ preventScroll: true });
      return;
    }
    found.focus({ preventScroll: true });
    if (found instanceof HTMLInputElement) {
      // A list only ever sends the caret into a field in order to replace that field. The one field
      // this reaches is the rename editor, which opens carrying the title it is about to stand in
      // for; selecting it makes typing replace the name, which is what renaming a thing means
      // everywhere else, and makes one Backspace the way to clear a custom title back to the
      // derived one, which is the empty submit the switcher already accepts. Bare focus puts the
      // caret at the end instead (measured in Chromium: offset 28 of "Everything about model
      // swaps"), so the reader has to select the name by hand before they can say a new one.
      // Deliberately not applied to the anchor: that is a landing place the list fell back to, not
      // a control it chose, and the composer's draft is a sentence somebody is writing.
      found.select();
    }
  }, [handoff, list, anchor]);
  return useCallback((key: string | null) => {
    wanted.current = { key };
    setHandoff((asked) => asked + 1);
  }, []);
}
