
import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef } from "react";

import { rideTail } from "./logRide";
import { MORPH_START_EVENT } from "./morph";

/** How close to the bottom (px) still counts as "reading the tail". Two things are spent on it: the
 *  auto-scroll follows a landing reply for a reader inside it, and a section rolling open inside the
 *  log holds their distance from the tail instead of pushing it away (`logRide.ts`). */
const PIN_THRESHOLD_PX = 40;

export interface LogScroll {
  /** Goes on the scrolling box, which is mounted with the view and never unmounted. */
  readonly ref: RefObject<HTMLDivElement>;
  /** Goes on that box's `onScroll`. */
  readonly onScroll: () => void;
  /** Put the log on its tail, if the tail is where the reader is. Stable identity, so the
   *  composer's measurement does not re-subscribe on every frame of a stream. */
  readonly toTail: () => void;
}

/** Hold the log where the reader put it, across everything that would otherwise move it. */
export function useLogScroll(showing: boolean, columnRef: RefObject<HTMLElement | null>): LogScroll {
  const ref = useRef<HTMLDivElement>(null!);
  const pinned = useRef(true);
  const parked = useRef(0);
  // Read from a DOM event, so it has to be the CURRENT answer rather than the one a closure was
  // built with. Assigned during the render, so it is already right by the time anything this render
  // scheduled can fire.
  const onScreen = useRef(showing);
  onScreen.current = showing;

  const onScroll = useCallback(() => {
    if (!onScreen.current) {
      return;
    }
    const el = ref.current;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight <= PIN_THRESHOLD_PX;
    parked.current = el.scrollTop;
  }, []);

  // "The reader is at the tail" is a claim about the log that has to survive everything that can
  // falsify it, so the one way of restoring it is shared.
  const toTail = useCallback(() => {
    if (pinned.current) {
      const el = ref.current;
      el.scrollTop = el.scrollHeight;
    }
  }, []);

  useLayoutEffect(() => {
    if (showing) {
      ref.current.scrollTop = parked.current;
      toTail();
    }
  }, [showing, toTail]);

  const ride = useRef<(() => void) | null>(null);
  useEffect(() => {
    const box = ref.current;
    const column = columnRef.current;
    const onRoll = (event: Event) => {
      const section = event.target as HTMLElement;
      // A roll starting while another is still in the air re-reads the distance from where the eye
      // has the log now, rather than carrying a baseline measured against a layout that has since
      // moved on.
      ride.current?.();
      ride.current = rideTail(box, section, PIN_THRESHOLD_PX);
    };
    column?.addEventListener(MORPH_START_EVENT, onRoll);
    return () => {
      column?.removeEventListener(MORPH_START_EVENT, onRoll);
      ride.current?.();
    };
  }, [columnRef]);

  return { ref, onScroll, toTail };
}
