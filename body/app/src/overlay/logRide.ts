
import { MIN_DELTA_PX, MORPHING_ATTRIBUTE } from "./morph";

/**
 * Where `box` must sit for `tail` px of content to stay below its bottom edge, capped so that
 * `section`'s own top edge stays on screen.
 */
function stopAt(box: HTMLElement, section: HTMLElement, tail: number): number {
  const room = section.getBoundingClientRect().top - box.getBoundingClientRect().top;
  // Room is spent, not kept: a section already above the window's top edge caps the ride where it
  // stands, since scrolling further down carries the reader away from the thing they just opened.
  const cap = box.scrollTop + Math.max(room, 0);
  // The floor is the engine's: a position past either end of the range is clamped to it, which is
  // also what the read-back below is for.
  return Math.min(box.scrollHeight - box.clientHeight - tail, cap);
}

/**
 * Hold `box`'s distance from the end of its content for every frame of the roll now running in
 * `section`, for a reader already `within` px of that end. Answers the way to call the ride off.
 */
export function rideTail(box: HTMLElement, section: HTMLElement, within: number): () => void {
  // The distance being held, learned on the first frame rather than given: see below.
  let tail: number | null = null;
  // What this ride last put on the box, so a scroll that did not come from here can be told apart
  // from one that did.
  let wrote = 0;
  let frame: number | null = null;
  const step = (): void => {
    const range = box.scrollHeight - box.clientHeight;
    if (tail === null) {
      tail = range - box.scrollTop;
      if (tail > within) {
        frame = null;
        return;
      }
    } else if (Math.abs(box.scrollTop - Math.min(wrote, range)) >= MIN_DELTA_PX) {
      frame = null;
      return;
    } else {
      box.scrollTop = stopAt(box, section, tail);
    }
    // Read back rather than remembered: the engine clamps a scroll position to the range it has, so
    // what was asked for and what the box took are not always the same number.
    wrote = box.scrollTop;
    frame =
      section.isConnected && section.hasAttribute(MORPHING_ATTRIBUTE)
        ? requestAnimationFrame(step)
        : null;
  };
  frame = requestAnimationFrame(step);
  return () => {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
    }
  };
}
