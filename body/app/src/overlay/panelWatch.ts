
import { MORPHING_ATTRIBUTE } from "./morph";
import { type Memory, heightOf } from "./panelMemory";

/** Whether something is already moving the panel's height, and this resize is its doing. */
function owned(element: HTMLElement, memory: Memory): boolean {
  if (element.querySelector(`[${MORPHING_ATTRIBUTE}]`) !== null) {
    return true;
  }
  return memory.running !== null && memory.running.playState === "running";
}

/**
 * Watch `element` and `replace` its placement whenever its own content resizes it.
 *
 * `replace` is the same placement the roll's end event drives, so the panel eases its content's
 * growth from wherever it is, exactly as it eases growth a render told it about.
 */
export function watchSize(element: HTMLElement, memory: Memory, replace: () => void): () => void {
  // The height this watch last looked at. Not the height the panel was PLACED at: a roll and an
  // ease both walk the box past this every frame, and what matters each time is only whether
  // anything has moved since the last reading.
  let seen = heightOf(element);
  let rearm: number | null = null;
  const observer = new ResizeObserver(() => {
    const height = heightOf(element);
    if (height === seen) {
      return;
    }
    seen = height;
    if (owned(element, memory)) {
      return;
    }
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
