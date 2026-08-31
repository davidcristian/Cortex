import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { MORPH_END_EVENT, MORPH_START_EVENT } from "./morph";
import { type Placement, emptyMemory, touched } from "./panelMemory";
import { place } from "./panelPlacement";
import { watchSize } from "./panelWatch";

/** The three ways the user reaches the panel: a press, a key, or an activation with neither, which
 *  is how assistive technology and scripts click a button. Any of them ends the summon's hold on
 *  the geometry, so a section opened a beat later grows from the edge the panel is held to. */
const TOUCH_EVENTS = ["pointerdown", "keydown", "click"] as const;

/** Own `ref`'s vertical geometry: how tall the panel is and how far off the bottom it sits. The
 *  rules and the arithmetic are in `panelPlacement` and `panelGeometry`; this is only about when
 *  the panel is placed, and it runs on every render because any DOM change can resize it. */
export function usePanelMotion(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  view: string,
): void {
  // Seeded with the panel's starting state, so the first summon reads as one.
  const memory = useRef(emptyMemory(open, view));
  // What the panel is being placed for, held where a listener can read the current values rather
  // than the ones its closure was built with. A roll announces its start from a layout effect,
  // before any passive effect of that render has re-subscribed. Assigned during the render.
  const at = useRef<Placement>({ open, view, recentre: false });
  at.current = { open, view, recentre: false };

  useLayoutEffect(() => {
    place(ref.current, memory.current, at.current);
  });

  useEffect(() => {
    // The centred position is a fraction of the viewport, so a resized window is a re-centre.
    const onResize = () => place(ref.current, memory.current, { ...at.current, recentre: true });
    // Both ends of a section's roll, because a roll is not always a render the panel sees: a
    // reply's Thoughts disclosure owns its open state locally.
    const onMorph = () => place(ref.current, memory.current, at.current);
    // Listened for in the capture phase and on the window, so no handler in between can keep the
    // event from the panel by stopping it.
    const onTouch = () => touched(memory.current);
    const element = ref.current;
    window.addEventListener("resize", onResize);
    for (const name of TOUCH_EVENTS) {
      window.addEventListener(name, onTouch, true);
    }
    element?.addEventListener(MORPH_START_EVENT, onMorph);
    element?.addEventListener(MORPH_END_EVENT, onMorph);
    // And the resizes nothing announces at all: a released row, or content that settles after the
    // render that brought it.
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
    // The panel element is mounted for the life of the overlay, so this subscribes once, and the
    // handlers read everything that changes from `at` above.
  }, [ref]);
}
