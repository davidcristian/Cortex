// The watch the panel keeps on its own box, for the resizes nothing else announces.
//
// `usePanelMotion` places the panel on renders of `Panel`, on both ends of a section's roll, and on
// a window resize. Content that resizes the panel without any of those leaves the last placement
// standing: a draft growing a line lives in the composer's own state, so nothing above the composer
// renders and the panel's `auto` height simply follows in the frame the character lands, bottom edge
// pinned, with no ease at all. A row released at the end of its exit is the same shape (the release
// is state inside the list, not above it), and so is any content that settles after the render that
// brought it.
//
// A `ResizeObserver` on the panel closes that gap, and the whole design of it is what it must NOT
// react to, because every placement resizes the element being watched.
//
// **A roll owns the height.** While a section inside is animating its own height, the panel's `auto`
// height follows it frame by frame, which is one notification per frame for the length of the roll
// (measured at 900x900 over the demo's reminder pull: 19 notifications across a 300ms roll). Placing
// on those would put the panel's own arithmetic against a height that is mid-animation by
// construction, and the ride-along has already taken the bottom edge to where the roll will leave
// it.
//
// **A move of the panel's own owns the height too.** The panel's ease is a height animation on this
// same element, so it is also one notification per frame (18 across one 380ms move in the same
// trace). Placing on those feeds the observer its own output: each one would cancel the running ease
// to measure the natural box and start another, sixty times a second, which is the mid-stream
// retarget already filed as a refinement, arriving once per frame instead of once per token.
//
// **A reading with nothing behind it is answered with nothing.** The watch remembers the height it
// last looked at, which is not the height the panel was placed at: a roll and an ease both walk the
// box past it every frame, and the only question each time is whether anything has moved since. It
// is what settles the callback rather than letting it chase the box it just moved.
//
// What is left is exactly the case the observer is for: the panel's box changed while nothing was
// moving it.
//
// **And the watch is lifted for the frame the panel writes in.** Placing is itself a resize of the
// element being watched: the ease starts at the height the panel HAD, so the box the notification
// reported is not the box the frame paints. An observer whose callback resizes its own target is
// the one case the specification's depth rule cannot deliver, since the re-gathered observation is
// no deeper than the broadcast that caused it, so the notification is dropped and the page is told
// through the "loop completed with undelivered notifications" error. Measured over the demo, that
// was one error event per keystroke that grew the pill. Dropping the observation before placing and
// taking it up again on the next frame leaves nothing to re-gather, so the error never fires; the
// reading that arrives when the watch is taken up again is answered by the rules above, the panel's
// own ease being in the air by then.
//
// The ease itself is NOT a frame late for this. Traced at 640x720 over a Shift+Enter that restacks
// the pill: `requestAnimationFrame` runs before the resize observer steps, so a trace taken there
// reads 404 for the frame the character landed, while a probe reading the same frame AFTER the
// placement reads 352 with one animation attached. The frame paints the height the panel had and
// eases from it; nothing jumps and comes back.

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
