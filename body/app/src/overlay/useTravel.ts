// Rows that travel to the place a commit moved them to, instead of being there already. The
// mechanism is the one usually called FLIP: read where each row is, let the commit put it where it
// belongs, and give the difference back as a transform that decays to nothing over a roll's clock.

import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";

/** The rows to watch, in the order the list renders them. */
function rowsIn(list: HTMLElement, rows: string): HTMLElement[] {
  return [...list.querySelectorAll<HTMLElement>(rows)];
}

/** Animate every row under `list` matching `rows` from where it was to where a commit has put it.
 *  Positions come from `offsetTop`, which is layout and therefore blind to the transforms this
 *  writes and to the list's own scrolling. A row is remembered by its element, not by a key. */
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
      // A row seen for the first time has nowhere to travel from, and neither has one that moved
      // by less than a rounding wobble.
      if (was === undefined || Math.abs(was - now) < MIN_DELTA_PX || reduce) {
        continue;
      }
      row.animate(
        [{ transform: `translateY(${was - now}px)` }, { transform: "translateY(0px)" }],
        { duration: MORPH_ROLL_MS, easing: EASING, composite: "add" },
      );
    }
    // A roll inside the list moves rows without committing anything, so the record follows it
    // frame by frame and animates nothing from it: the next commit would otherwise read the whole
    // roll as one jump. One loop at a time.
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
  // a roll is still running inside it. The handle is forgotten as well as cancelled, so a mount
  // that is torn down and set up again is not left holding a frame that never arrives.
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
