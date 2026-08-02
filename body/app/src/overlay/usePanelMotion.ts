import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { MORPH_END_EVENT, MORPH_START_EVENT } from "./morph";
import { type Placement, emptyMemory, touched } from "./panelMemory";
import { place } from "./panelPlacement";
import { watchSize } from "./panelWatch";

/** The three ways the user reaches the panel: a press, a key, or an activation that arrives
 *  without either, which is how assistive technology and scripts click a button. Any of them ends
 *  the summon's hold on the geometry, so a section rolled open a beat after the panel appeared
 *  grows from the pinned edge like any other and gives that edge back when it rolls shut. */
const TOUCH_EVENTS = ["pointerdown", "keydown", "click"] as const;

/**
 * Own `ref`'s vertical geometry: how tall the panel is and how far off the bottom it sits.
 *
 * The rules and the arithmetic live in `panelPlacement` and `panelGeometry`; this is the React half,
 * which is only about WHEN the panel is placed. It runs on every render (no dependency list on
 * purpose): the trigger is not one piece of state but any DOM change that resized the element.
 * `useLayoutEffect` reads the new geometry after the DOM is updated and before the browser paints,
 * so the animation starts from what the eye last saw rather than from the finished layout.
 *
 * `view` names which of the panel's faces is showing, and nothing finer: `"chat"` covers every
 * conversation, because opening a different chat or minting a new one changes what is in the panel
 * and not which panel it is, so it grows and shrinks from the pinned edge like any other size
 * change. Entering another view centres it; returning to `"chat"` restores the edge it was left at.
 * `open` is false while the panel is closed or minimized, where the size is not what moves: the
 * open/close pop and the corner travel are transforms and own that motion themselves. Under
 * `prefers-reduced-motion` nothing is scheduled at all.
 *
 * Three things here are not renders. A summon owns the panel's geometry for a window afterwards,
 * and any input inside that window ends it early (`touched`). A section's roll brackets itself with
 * its own two events, because a roll is not always a render the panel sees. And the panel watches
 * its own box (`panelWatch`), for the resizes that are neither: a draft growing a line lives in the
 * composer's own state, so nothing above it renders and the panel's `auto` height would otherwise
 * simply follow in the frame the character lands.
 */
export function usePanelMotion(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  view: string,
): void {
  // Seeded with the panel's starting state, so the first summon reads as one and a panel that was
  // already open on mount does not.
  const memory = useRef(emptyMemory(open, view));
  // What the panel is being placed FOR, held where a listener can read the CURRENT values instead
  // of the ones its closure was built with. A roll announces its start from inside a layout effect,
  // which is before any passive effect of that same render has re-subscribed, so a handler closed
  // over `open` and `view` would place the panel for the render before the one on screen. Assigned
  // during the render, so it is already current by the time any effect of that render runs.
  const at = useRef<Placement>({ open, view, recentre: false });
  at.current = { open, view, recentre: false };

  useLayoutEffect(() => {
    place(ref.current, memory.current, at.current);
  });

  useEffect(() => {
    // The centred position is a fraction of the viewport, so a resized window is a re-centre.
    const onResize = () => place(ref.current, memory.current, { ...at.current, recentre: true });
    // Both ends of a section's roll, because a roll is not always a render the panel sees: the
    // sections in its own chrome open and shut on overlay state, but a reply's Thoughts disclosure
    // owns its open state locally and nothing above that message re-renders when it is clicked. On
    // the START the panel takes its bottom edge along with the roll (`rideAlong`) instead of moving
    // in a second beat once the roll has landed; on the END it picks its own geometry back up, a
    // roll open having changed no state that would otherwise say it is taller now.
    const onMorph = () => place(ref.current, memory.current, at.current);
    // Listened for in the CAPTURE phase and on the window, so no handler in between can hide the
    // user's hand from the panel by stopping the event: the keys that open a section are handled
    // wherever they are handled, and this only wants to know that one was pressed at all.
    const onTouch = () => touched(memory.current);
    const element = ref.current;
    window.addEventListener("resize", onResize);
    for (const name of TOUCH_EVENTS) {
      window.addEventListener(name, onTouch, true);
    }
    element?.addEventListener(MORPH_START_EVENT, onMorph);
    element?.addEventListener(MORPH_END_EVENT, onMorph);
    // And the resizes nothing announces at all: a draft growing a line, a released row, content
    // that settles after the render that brought it. `panelWatch` decides which of the panel's own
    // size changes are its content moving and which are a roll or its own ease, and drives the same
    // placement the roll's end event does for the first kind only.
    const unwatch = element === null ? null : watchSize(element, memory.current, onMorph);
    return () => {
      window.removeEventListener("resize", onResize);
      for (const name of TOUCH_EVENTS) {
        window.removeEventListener(name, onTouch, true);
      }
      element?.removeEventListener(MORPH_START_EVENT, onMorph);
      element?.removeEventListener(MORPH_END_EVENT, onMorph);
      unwatch?.();
    };
    // The panel element is mounted for the life of the overlay, so this subscribes once. Everything
    // the handlers need that does change is read from `at` above, which is why this list no longer
    // carries `open` and `view`: re-subscribing on them was what made the handlers look current.
  }, [ref]);
}
