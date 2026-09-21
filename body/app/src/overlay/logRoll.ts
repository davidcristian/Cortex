// The scroll the history makes while a section rolls open or shut inside it. At the panel's
// ceiling the panel cannot grow, so the section's growth comes out of the log's scroll range
// instead and the end of the reply slides out under the composer.

import { MIN_DELTA_PX, MORPHING_ATTRIBUTE } from "./morph";

/** Where `box` must be for `tail` px of content to stay below its bottom edge, capped so that
 *  `section`'s own top edge stays on screen. The cap only ever binds for a section inside the box:
 *  for one in the panel's chrome the room is negative, so the scroll stays where it started. */
function stopAt(box: HTMLElement, section: HTMLElement, tail: number): number {
  const hold = box.scrollHeight - box.clientHeight - tail;
  if (!box.contains(section)) {
    return hold;
  }
  const room = section.getBoundingClientRect().top - box.getBoundingClientRect().top;
  // Room is used up rather than kept: a section already above the window's top edge stops the
  // scroll where it is, since going further down takes the reader away from what they opened.
  const cap = box.scrollTop + Math.max(room, 0);
  return Math.min(hold, cap);
}

/** Hold `box`'s distance from the end of its content for every frame of the roll now running in
 *  `section`, for a reader already `within` px of that end, and return the way to stop. `within`
 *  is the log's own threshold, passed in: the two must be the same number. */
export function holdTail(box: HTMLElement, section: HTMLElement, within: number): () => void {
  // The distance being held, read on the first frame rather than given.
  let tail: number | null = null;
  // What this function last wrote, so a scroll that came from somewhere else can be told apart.
  let wrote = 0;
  let frame: number | null = null;
  const step = (): void => {
    const range = box.scrollHeight - box.clientHeight;
    if (tail === null) {
      // The roll's own frame zero, where the section still stands at the height it is rolling
      // from, so this is the "before" reading. It is also the last moment the reader's own
      // distance from the end can be read, which is why the threshold is tested here.
      tail = range - box.scrollTop;
      if (tail > within) {
        frame = null;
        return;
      }
    } else if (Math.abs(box.scrollTop - Math.min(wrote, range)) >= MIN_DELTA_PX) {
      // Someone else has the scroll: the reader's wheel, or a reply that arrived mid-roll. Either
      // outranks this, which stops rather than competing. Compared against what was last written
      // and clamped to the range the box has now, because a closing roll shortens the content.
      frame = null;
      return;
    } else {
      box.scrollTop = stopAt(box, section, tail);
    }
    // Read back rather than remembered: the engine clamps a scroll position to the range it has.
    wrote = box.scrollTop;
    // Work first and decide after, so the frame that finds the roll over has already settled the
    // scroll: `Collapse` clears the attribute before it reports the end. The section can also leave
    // the tree mid-roll, and a loop reading a detached tree would never stop.
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
