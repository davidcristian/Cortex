import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { MORPH_END_EVENT, MORPH_START_EVENT } from "./morph";
import { type Placement, emptyMemory, touched } from "./panelMemory";
import { place } from "./panelPlacement";

/**
 * The three ways the user reaches the panel: a press, a key, or an activation that arrives without
 * either, which is how assistive technology and scripts click a button.
 */
const TOUCH_EVENTS = ["pointerdown", "keydown", "click"] as const;

/** Own `ref`'s vertical geometry: how tall the panel is and how far off the bottom it sits. */
export function usePanelMotion(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  view: string,
): void {
  // Seeded with the panel's starting state, so the first summon reads as one and a panel that was
  // already open on mount does not.
  const memory = useRef(emptyMemory(open, view));
  const at = useRef<Placement>({ open, view, recentre: false });
  at.current = { open, view, recentre: false };

  useLayoutEffect(() => {
    place(ref.current, memory.current, at.current);
  });

  useEffect(() => {
    // The centred position is a fraction of the viewport, so a resized window is a re-centre.
    const onResize = () => place(ref.current, memory.current, { ...at.current, recentre: true });
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
    return () => {
      window.removeEventListener("resize", onResize);
      for (const name of TOUCH_EVENTS) {
        window.removeEventListener(name, onTouch, true);
      }
      element?.removeEventListener(MORPH_START_EVENT, onMorph);
      element?.removeEventListener(MORPH_END_EVENT, onMorph);
    };
    // The panel element is mounted for the life of the overlay, so this subscribes once. Everything
    // the handlers need that does change is read from `at` above, which is why this list no longer
    // carries `open` and `view`: re-subscribing on them was what made the handlers look current.
  }, [ref]);
}
