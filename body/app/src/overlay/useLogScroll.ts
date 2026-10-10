// Where the reader is in the conversation, and keeping them there. Two separate claims: whether
// the reader is following the end of the log, and which line they are on otherwise. Both are refs,
// because both are about the DOM and neither should re-render anything when it changes.

import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef } from "react";

import { holdTail } from "./logRoll";
import { MORPHING_ATTRIBUTE, MORPH_START_EVENT } from "./morph";
import { SCROLL_CLAMPED_EVENT } from "./panelParts";

/** How close to the bottom (px) still counts as "reading the tail". Two things use it: the
 *  auto-scroll follows a reply for a reader inside it, and a section rolling open inside the log
 *  holds their distance from the end instead of pushing it away. */
const TAIL_THRESHOLD_PX = 40;

export interface LogScroll {
  /** Goes on the scrolling box, which is mounted with the view and never unmounted. */
  readonly ref: RefObject<HTMLDivElement>;
  /** Goes on that box's `onScroll`. */
  readonly onScroll: () => void;
  /** Put the log on its tail, if the tail is where the reader is. Stable identity, so the
   *  composer's measurement does not re-subscribe on every frame of a stream. */
  readonly toTail: () => void;
}

/** Hold the log where the reader put it, across everything that would otherwise move it. `showing`
 *  is whether the chat is the view on screen, because the trip to the console takes the scroll
 *  position with it. `columnRef` is the flex column this box is in, where a roll is heard. */
export function useLogScroll(showing: boolean, columnRef: RefObject<HTMLElement | null>): LogScroll {
  const ref = useRef<HTMLDivElement>(null!);
  const onTail = useRef(true);
  const parked = useRef(0);
  // Where the box was when this hook or the panel's measurement last moved it, or it heard it move.
  // A scroll event that finds it still there did not come from the reader, so it keeps the following.
  const left = useRef(0);
  // Read from a DOM event, so it has to be the current answer rather than the one a closure was
  // built with. Assigned during the render, so it is right before anything this render scheduled.
  const onScreen = useRef(showing);
  onScreen.current = showing;

  const onScroll = useCallback(() => {
    if (!onScreen.current) {
      return;
    }
    const el = ref.current;
    if (el.scrollHeight - el.scrollTop - el.clientHeight <= TAIL_THRESHOLD_PX) {
      onTail.current = true;
    } else if (Math.abs(el.scrollTop - left.current) >= 1) {
      onTail.current = false;
    }
    left.current = el.scrollTop;
    parked.current = el.scrollTop;
  }, []);

  const toTail = useCallback(() => {
    if (onTail.current) {
      const el = ref.current;
      el.scrollTop = el.scrollHeight;
      left.current = el.scrollTop;
    }
  }, []);

  // Coming back: give the log the place the trip took from it, before the browser paints, then
  // put it back on its end, because a reply can arrive while the console is up.
  useLayoutEffect(() => {
    if (showing) {
      ref.current.scrollTop = parked.current;
      toTail();
    }
  }, [showing, toTail]);

  // The box changes size with nothing scrolling it: on a fresh start the panel places its height
  // after the window takes its size, the log gets shorter and no scroll event fires.
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      // A roll's frames belong to `logRoll.ts`, which may be holding the reader off the end.
      if (columnRef.current?.querySelector(`[${MORPHING_ATTRIBUTE}]`) == null) {
        toTail();
      }
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [columnRef, toTail]);

  // The panel measures itself at its new height, where a growing log has a shorter range, and the
  // engine moves the box to fit it while the eye still has the old height.
  useEffect(() => {
    const box = ref.current;
    const onClamped = () => {
      left.current = box.scrollTop;
    };
    box.addEventListener(SCROLL_CLAMPED_EVENT, onClamped);
    return () => box.removeEventListener(SCROLL_CLAMPED_EVENT, onClamped);
  }, []);

  // Subscribed on the column rather than on the box, because half the rolls that shrink this log
  // happen outside it: the switcher list and the reminder stack are siblings, so their bubbling
  // event goes up past the log and the box never hears it.
  const hold = useRef<(() => void) | null>(null);
  useEffect(() => {
    const box = ref.current;
    const column = columnRef.current;
    const onRoll = (event: Event) => {
      // The roll's own element, which is what the event's target is. Reading the target rather
      // than searching for the attribute keeps two rolls in one frame apart.
      const section = event.target as HTMLElement;
      // A roll starting while another is still running re-reads the distance from where the eye
      // has the log now.
      hold.current?.();
      hold.current = holdTail(box, section, TAIL_THRESHOLD_PX);
    };
    column?.addEventListener(MORPH_START_EVENT, onRoll);
    return () => {
      column?.removeEventListener(MORPH_START_EVENT, onRoll);
      hold.current?.();
    };
  }, [columnRef]);

  return { ref, onScroll, toTail };
}
