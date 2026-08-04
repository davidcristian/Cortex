// Where the reader is in the conversation, and keeping them there.
//
// Two claims live here, and they are separate: whether the reader is following the tail (so a
// landing reply should scroll to it), and which line they are on otherwise (so a trip to the console
// gives it back). Both are refs, because both are about the DOM rather than about what is rendered,
// and neither should re-render anything when it changes.

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

/**
 * Hold the log where the reader put it, across everything that would otherwise move it.
 *
 * `showing` is whether the chat is the view on screen. It matters because the trip to the console
 * takes the scroll position: the view being left goes `display: none` a morph after it leaves, and
 * an unrendered box does not have one. Traced at 60Hz at 640x720 with the log a third of the way
 * up, 154 of 463 became 0 in the frame the class changed.
 *
 * So the position is parked on the way out and handed back on the way in, before the return is
 * painted. The scrolling the trip itself does is not the reader's and is ignored, which is what the
 * ref below is for: taking it would park the log wherever the trip left it, and a box with nothing
 * to scroll reads as a box sitting at its own tail, so it would re-pin it too. The trip used to do
 * plenty: the leaving view was laid out at its own natural height rather than the panel's, which
 * handed the history its whole content as its window and clamped `scrollTop` to zero a whole morph
 * before `display: none` got to it. That is `.view.out`'s job now, and this is still the half that
 * cannot be done in CSS.
 *
 * `columnRef` is the flex column this box stands in, which is the panel's chat face: the header, the
 * two roll-open sections, this log, the composer and the hint strip. It is where a roll is heard,
 * for the reason written over the subscription below, and it is handed in rather than walked to
 * from the box because the element belongs to the panel and not to the log.
 */
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

  // And the third thing that can falsify it: a section rolling open. A Thoughts trace grows in the
  // middle of a settled reply, and once the panel is at its ceiling that growth comes out of the
  // visible window rather than out of the panel, taking the end of the reply below the fold.
  // `rideTail` holds the reader's distance from the tail across the roll, for a reader who is at
  // the tail; anyone who has scrolled up keeps the row under the pointer that opened it, which is
  // the disclosure's own default and moves nothing they are reading. The threshold is this hook's,
  // the same one the pin is drawn at, and the ride tests it against the box itself on the roll's
  // first frame, that being the one moment in a roll where the log is still the size it was.
  //
  // Subscribed on the COLUMN rather than on the box, because half the rolls that shrink this log
  // happen outside it. The switcher list and the reminder stack are siblings of the box, not
  // children of it, so their bubbling start event goes up past the log to the panel and the box
  // never hears a thing; at the ceiling their growth comes out of the log's window exactly as a
  // trace's does, and measured at 640x720 on a full history, opening the switcher took the window
  // 293px to 73px with `scrollTop` untouched, so the end of the reply went 3px below the fold to
  // 223px. One listener on the element they share hears both, and a roll inside the log still
  // reaches it by bubbling through the box on its way. Which of the two a section is, the ride asks
  // the box itself (`logRide.ts`): only a section INSIDE it is something the reader can be carried
  // away from.
  const ride = useRef<(() => void) | null>(null);
  useEffect(() => {
    const box = ref.current;
    const column = columnRef.current;
    const onRoll = (event: Event) => {
      // The roll's own element, which is what the event's target IS: both dispatchers mark the
      // element they then announce from, and the contract says so (`morph.ts`). Reading the target
      // rather than searching for the mark is what keeps two rolls in one frame apart, a switcher
      // row leaving under an empty line arriving being the pair that does it.
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
