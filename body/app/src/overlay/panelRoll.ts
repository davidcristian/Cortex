// The slide the panel makes alongside a section rolling open or shut inside it. The section owns
// the height while it rolls, and this is the only thing the panel does about it.

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";
import { centred, clamped, frame, maxHeight, openHeight } from "./panelGeometry";
import { type Memory, heightOf, measure } from "./panelMemory";
import { centringHeight } from "./panelParts";

/** Slide the bottom edge to where the roll now running will leave it, over that same roll. The
 *  panel will be as tall as it is now, less what the section takes now, plus what it is about to
 *  take, capped at its own `max-height`: a prediction it cannot reach is a height it never has. */
export function rideAlong(
  element: HTMLElement,
  memory: Memory,
  section: HTMLElement,
  viewport: number,
  arrival: boolean,
): void {
  // Read the box before cancelling and again after: a running animation overrides the properties
  // it animates, so the first read is what the eye has and the second is the panel's own layout.
  const live = memory.running !== null && memory.running.playState === "running";
  const shown = live ? measure(element, viewport) : null;
  memory.running?.cancel();
  memory.running = null;
  const natural = heightOf(element);
  const target = Number(section.getAttribute(MORPHING_ATTRIBUTE));
  const raw = natural - heightOf(section) + target;
  if (arrival) {
    // The summon is still arriving, so this roll is part of the panel appearing and ends centred
    // on the height it takes the panel to. Counted through `centringHeight` and bounded at the
    // loose cap, both as the placement at the end of the roll does, so the two agree.
    memory.pinned = centred(viewport, centringHeight(element, Math.min(raw, openHeight(viewport))));
  }
  const bottom = clamped(memory.pinned);
  const ceiling = maxHeight(viewport, bottom);
  // The height this roll leaves the panel at, under the ceiling of the edge it now stands on.
  const height = Math.min(raw, ceiling);
  const from = shown?.bottom ?? memory.applied;
  // Only a height ease has to be taken over; a slide of the bottom edge alone leaves the height to
  // the section anyway. An arrival whose section outgrows the ceiling is the other case: driven
  // from here, the chat's window compresses as the stack grows instead of only at the end.
  const squeezed = arrival && raw > ceiling ? natural : null;
  const carried =
    shown !== null && Math.abs(shown.height - natural) >= MIN_DELTA_PX ? shown.height : squeezed;
  memory.carrying = carried === null ? null : height;
  memory.applied = bottom;
  // With its fraction, for the reason `panelPlacement` gives where it writes the same edge.
  element.style.bottom = `${bottom}px`;
  if (carried === null && Math.abs(bottom - from) < MIN_DELTA_PX) {
    // The common case: nothing of the panel's own was moving and it is nowhere near its ceiling,
    // so the roll is the whole movement.
    return;
  }
  // Where this slide ends and when, in the same terms as the panel's own moves, so a placement
  // that arrives mid-slide and is going to the same place resumes it rather than restarting it.
  memory.aim = { height, bottom };
  memory.lands = Date.now() + MORPH_ROLL_MS;
  memory.running = element.animate(
    carried === null
      ? [{ bottom: `${from}px` }, { bottom: `${bottom}px` }]
      : // The `carried` ease starts from a height the roll's own ceiling may already forbid, so
        // the ceiling goes with it rather than clamping it flat on the first frame.
        [frame(carried, from, Math.max(carried, ceiling)), frame(height, bottom, ceiling)],
    { duration: MORPH_ROLL_MS, easing: EASING },
  );
}
