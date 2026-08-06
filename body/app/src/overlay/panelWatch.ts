// The watch the panel keeps on its own box, for the resizes nothing else announces. The whole
// design of it is what it must not react to, because every placement resizes the element being
// watched: a roll owns the height, and a reading that matches `placedFor` has nothing behind it.

import { MORPHING_ATTRIBUTE } from "./morph";
import { type Memory, heightOf, naturalHeightOf } from "./panelMemory";

/** Whether a section inside is rolling, which owns the height for as long as it runs. */
function rolling(element: HTMLElement): boolean {
  return element.querySelector(`[${MORPHING_ATTRIBUTE}]`) !== null;
}

/** The height the panel wants right now: what it would be with nothing animating it. Probed only
 *  while a move of its own is overriding the box, that being the one case the box cannot answer. */
function wanted(element: HTMLElement, memory: Memory): number {
  const moving = memory.running !== null && memory.running.playState === "running";
  return moving ? naturalHeightOf(element) : heightOf(element);
}

/** Watch `element` and `replace` its placement whenever its own content resizes it. `replace` is
 *  the same placement the roll's end event drives, so the panel eases its content's growth from
 *  wherever it is. */
export function watchSize(element: HTMLElement, memory: Memory, replace: () => void): () => void {
  let rearm: number | null = null;
  const observer = new ResizeObserver(() => {
    if (rolling(element)) {
      return;
    }
    if (wanted(element, memory) === memory.placedFor) {
      return;
    }
    // The watch is dropped for the frame the panel writes in. Placing resizes the element being
    // watched, and an observer whose callback resizes its own target is the one case the
    // specification cannot deliver: the notification is dropped and the page is told by an error.
    observer.unobserve(element);
    replace();
    rearm = requestAnimationFrame(() => {
      rearm = null;
      observer.observe(element);
    });
  });
  observer.observe(element);
  return () => {
    if (rearm !== null) {
      cancelAnimationFrame(rearm);
    }
    observer.disconnect();
  };
}
