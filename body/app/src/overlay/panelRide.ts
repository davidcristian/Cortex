// The slide the panel makes alongside a section rolling open or shut inside it. The section owns
// the height while it rolls (`morph.ts`); this is the only thing the panel does about it.

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";
import { centred, clamped, frame, maxHeight } from "./panelGeometry";
import { type Memory, heightOf, measure } from "./panelMemory";

/** Slide the bottom edge to where the roll now running will leave it, over that same roll. */
export function rideAlong(
  element: HTMLElement,
  memory: Memory,
  section: HTMLElement,
  viewport: number,
  arrival: boolean,
): void {
  // Read the box BEFORE cancelling and again after: a running animation overrides the properties it
  // animates, so the first read is what the eye has and the second is the panel's own layout.
  const live = memory.running !== null && memory.running.playState === "running";
  const shown = live ? measure(element, viewport) : null;
  memory.running?.cancel();
  memory.running = null;
  const natural = heightOf(element);
  const target = Number(section.getAttribute(MORPHING_ATTRIBUTE));
  const height = Math.min(natural - heightOf(section) + target, maxHeight(viewport, memory.applied));
  if (arrival) {
    // The summon is still landing, so this roll is part of the panel appearing rather than growth
    // after the fact: it ends centred on the height it is taking the panel to, and that is the edge
    // the session is then pinned to.
    memory.pinned = centred(viewport, height);
  }
  const bottom = clamped(memory.pinned);
  const from = shown?.bottom ?? memory.applied;
  // Only a HEIGHT ease has to be carried. The other thing that can be in the air here is a slide of
  // the bottom edge alone (an earlier ride-along), which leaves the height to the section anyway.
  const carried =
    shown !== null && Math.abs(shown.height - natural) >= MIN_DELTA_PX ? shown.height : null;
  memory.carrying = carried === null ? null : height;
  memory.applied = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  if (carried === null && Math.abs(bottom - from) < MIN_DELTA_PX) {
    // The common case by far: nothing of the panel's own was moving and it is nowhere near its
    // ceiling, so the roll is the whole movement and nothing else on screen moves at all.
    return;
  }
  memory.aim = { height, bottom };
  memory.lands = Date.now() + MORPH_ROLL_MS;
  memory.running = element.animate(
    carried === null
      ? [{ bottom: `${from}px` }, { bottom: `${bottom}px` }]
      : [frame(carried, from), frame(height, bottom)],
    { duration: MORPH_ROLL_MS, easing: EASING },
  );
}
