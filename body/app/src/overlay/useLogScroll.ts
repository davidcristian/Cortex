
import { type RefObject, useCallback, useLayoutEffect, useRef } from "react";

/** How close to the bottom (px) still counts as "reading the tail" for auto-scroll. */
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
export function useLogScroll(showing: boolean): LogScroll {
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

  return { ref, onScroll, toTail };
}
