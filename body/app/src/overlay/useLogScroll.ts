// Where the reader is in the conversation, and keeping them there.
//
// Two claims live here, and they are separate: whether the reader is following the tail (so a
// landing reply should scroll to it), and which line they are on otherwise (so a trip to the console
// gives it back). Both are refs, because both are about the DOM rather than about what is rendered,
// and neither should re-render anything when it changes.

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

/**
 * Hold the log where the reader put it, across everything that would otherwise move it.
 *
 * `showing` is whether the chat is the view on screen. It matters because the trip to the console
 * takes the scroll position: the view being left is lifted out of the layout flow (`.view.out`),
 * which hands the history its whole content as its window, and a box with nothing left to scroll is
 * clamped to zero by the engine; a morph later `.view.gone` is `display: none`, which zeroes it a
 * second time. Traced at 60Hz at 640x720 with the log a third of the way up: 154 of 463 in the last
 * frame before the class changed, then 0 against a 463px window in the first frame after it.
 *
 * So the position is parked on the way out and handed back on the way in, before the return is
 * painted. The scrolling the trip itself does is not the reader's and is ignored, which is what the
 * ref below is for: taking it would park the log wherever the trip left it, and a box with nothing
 * to scroll reads as a box sitting at its own tail, so it would re-pin it too.
 */
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

  // Coming back: hand the log the place the trip took from it, before the browser paints, so the
  // return is the conversation as it was left rather than as the layout left it. Then re-pin,
  // because a reply can land while the console is up, so a reader who was at the tail comes back to
  // the tail, which has moved, and everyone else comes back to their own line.
  useLayoutEffect(() => {
    if (showing) {
      ref.current.scrollTop = parked.current;
      toTail();
    }
  }, [showing, toTail]);

  return { ref, onScroll, toTail };
}
