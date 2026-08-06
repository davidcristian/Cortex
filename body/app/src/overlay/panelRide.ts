// The slide the panel makes alongside a section rolling open or shut inside it. The section owns
// the height while it rolls (`morph.ts`); this is the only thing the panel does about it.

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";
import { centred, clamped, frame, maxHeight, openHeight } from "./panelGeometry";
import { type Memory, heightOf, measure } from "./panelMemory";
import { centringHeight } from "./panelParts";

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
  const raw = natural - heightOf(section) + target;
  if (arrival) {
    memory.pinned = centred(viewport, centringHeight(element, Math.min(raw, openHeight(viewport))));
  }
  const bottom = clamped(memory.pinned);
  const ceiling = maxHeight(viewport, bottom);
  const height = Math.min(raw, ceiling);
  const from = shown?.bottom ?? memory.applied;
  const squeezed = arrival && raw > ceiling ? natural : null;
  const carried =
    shown !== null && Math.abs(shown.height - natural) >= MIN_DELTA_PX ? shown.height : squeezed;
  memory.carrying = carried === null ? null : height;
  memory.applied = bottom;
  // With its fraction, for the reason `panelPlacement` gives where it writes the same edge: the
  // slide below ends on this number and the element has to already be standing on it.
  element.style.bottom = `${bottom}px`;
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
      : // The carried ease starts from a height the roll's own ceiling may already forbid, so the
        // ceiling rides with it rather than clamping it flat on the first frame (see `frame`).
        [frame(carried, from, Math.max(carried, ceiling)), frame(height, bottom, ceiling)],
    { duration: MORPH_ROLL_MS, easing: EASING },
  );
}
