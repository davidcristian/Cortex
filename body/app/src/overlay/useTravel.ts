import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";

// Rows that travel to the place a commit moved them to, instead of being there already.
//
// The overlay had the two motions a list makes to a row it is losing or gaining: `Collapse` gives a
// section its own height animation, and `usePresence` holds a removed row on screen for the length
// of its exit. Neither covers the row that STAYS. The switcher re-lists pinned chats first and then
// by recency after every write, so pinning one regroups the list around it, and every row the
// regrouping touches was somewhere else in the previous frame and at its new place in this one.
// Traced at 900x900 before this existed: pinning the third of three chats took it 270 to 170 and
// pushed the two above it 50px each, the whole rearrangement inside the single frame the re-listing
// committed.
//
// The mechanism is the one usually called FLIP: read where each row IS, let the commit put it where
// it BELONGS, and hand the difference back as a transform that decays to nothing over the same
// clock and curve a roll uses. The transform is what lets a list do this without disturbing
// anything around it. Layout is already final in the frame the travel starts, so the card's height
// never changes, the panel's `auto` height has nothing to follow, and the watch the panel keeps on
// its own box (`panelWatch.ts`) has no resize to answer: a list motion that fought the panel's own
// ease would be a worse defect than the snap it removed.
//
// **A row is remembered by its element, not by a key.** React moves the DOM node a keyed row owns
// rather than rebuilding it, which is what makes a reorder a reorder; so the element IS the
// identity, and a row that was rebuilt (a chat that left and came back) is correctly a row with
// nowhere to travel from. That also means nothing has to be cleaned up: a `WeakMap` forgets an
// element the moment React drops it.
//
// **Where a row WAS is not always where the last commit left it.** A roll moves rows by LAYOUT,
// frame by frame, and no commit happens while it does: a deleted row's neighbours travel 50px over
// its 300ms exit and the next commit (the release, once the exit ends) would read that as a 50px
// jump to answer, sending them back down to re-travel a distance they had already covered. So while
// a roll is in flight inside the list, the record is refreshed every frame and nothing is played
// from it. The frame loop only remembers; only a commit may animate. That is also what puts a
// mid-roll regrouping on honest numbers, the leaving row included, since the position it is
// measured from is the one it had in the previous frame rather than the one it had 200ms ago.
//
// **An interrupted travel is composed, not cancelled.** A second regrouping landing mid-travel finds
// the row visually between two places and structurally at the second one, so cancelling the first
// animation to start a second would drop whatever of the first was left. Both are `composite: add`
// instead: each is a translation that decays to zero, so the offsets sum to exactly the gap the eye
// has and the row lands where layout already put it, whatever is still in the air.

/** The rows to watch, in the order the list renders them. */
function rowsIn(list: HTMLElement, rows: string): HTMLElement[] {
  return [...list.querySelectorAll<HTMLElement>(rows)];
}

/**
 * Animate every row under `list` matching `rows` from where it was to where a commit has put it.
 *
 * Positions are read with `offsetTop`, which is layout and therefore blind to the transforms this
 * hook writes and to the list's own scrolling, and which follows a rolling sibling's animated
 * height exactly as the eye does.
 */
export function useTravel(list: RefObject<HTMLElement | null>, rows: string): void {
  const places = useRef(new WeakMap<HTMLElement, number>());
  const frame = useRef<number | null>(null);

  useLayoutEffect(() => {
    const element = list.current;
    if (element === null) {
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    for (const row of rowsIn(element, rows)) {
      const now = row.offsetTop;
      const was = places.current.get(row);
      places.current.set(row, now);
      // A row seen for the first time has nowhere to travel from, and a row that moved by less than
      // a rounding wobble has nowhere worth travelling from either.
      if (was === undefined || Math.abs(was - now) < MIN_DELTA_PX || reduce) {
        continue;
      }
      row.animate(
        [{ transform: `translateY(${was - now}px)` }, { transform: "translateY(0px)" }],
        { duration: MORPH_ROLL_MS, easing: EASING, composite: "add" },
      );
    }
    // A roll inside the list moves rows without committing anything, so the record follows it frame
    // by frame and stops as soon as it ends. One loop at a time: a commit landing mid-roll finds it
    // already running and leaves it alone.
    if (frame.current !== null || element.querySelector(`[${MORPHING_ATTRIBUTE}]`) === null) {
      return;
    }
    const follow = (): void => {
      for (const row of rowsIn(element, rows)) {
        places.current.set(row, row.offsetTop);
      }
      frame.current =
        element.querySelector(`[${MORPHING_ATTRIBUTE}]`) === null
          ? null
          : requestAnimationFrame(follow);
    };
    frame.current = requestAnimationFrame(follow);
  });

  // The loop outlives the component otherwise: a switcher closed mid-exit unmounts this list while
  // a roll is still running inside it, and the callback would go on reading a detached tree. The
  // handle is forgotten as well as cancelled, so that a mount which is torn down and set up again
  // (which is what `StrictMode` does to every effect) is not left holding a frame that will never
  // arrive, blocking the next loop from ever starting.
  useEffect(
    () => () => {
      if (frame.current !== null) {
        cancelAnimationFrame(frame.current);
        frame.current = null;
      }
    },
    [],
  );
}
