// The slide the panel makes alongside a section rolling open or shut inside it. The section owns
// the height while it rolls (`morph.ts`); this is the only thing the panel does about it.

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";
import { centred, clamped, frame, maxHeight } from "./panelGeometry";
import { type Memory, heightOf, measure } from "./panelMemory";

/**
 * Slide the bottom edge to where the roll now running will leave it, over that same roll.
 *
 * A section rolling open can push the panel past the ceiling, and the panel is anchored by its
 * bottom edge, so something has to give: it grows downward instead. Doing that only once the roll
 * had ended made two beats out of one movement, and each beat overshot on its own. Traced at 60Hz:
 * opening the switcher on a panel already at its ceiling ran the top edge 12px off the top of the
 * screen and then slid the whole panel back down, and closing it dipped the top edge 120px and
 * brought it back up again. Riding along holds the top edge exactly still through both, which is
 * what the eye expects of a list rolling open underneath it.
 *
 * The section's target height is what makes this possible: the panel will be as tall as it is now,
 * less what the section takes now, plus what it is about to take. Capped at the panel's own
 * `max-height`, because a prediction the panel cannot reach places it for a height it will never
 * have: traced at 60Hz, opening the switcher on a full-height panel ran its bottom edge 108px down
 * to the floor of the screen over the roll and then brought it back, the arithmetic having been
 * asked where a 874px panel goes in a viewport that allows 684.
 *
 * **A move of the panel's own can still be in the air when a roll starts**: Ctrl+K while a reply
 * streams, or acking a reminder and reaching for the switcher inside the same 120ms. Cancelling that
 * height ease and handing the used height straight back to layout is a teleport, traced at 60Hz as
 * the top edge falling 61px in one frame with nothing animating it. So the interrupted ease is
 * CARRIED through instead, over the roll's own duration and curve, from where the eye has the panel
 * to where the roll will leave it. That curve is the section's own plus a residual that decays to
 * nothing by the end, which is why the panel can drive its height here without disagreeing with the
 * roll it is following. Composing the residual on top of the `auto` height would be neater and does
 * not work: measured in Chrome, an additive `height` animation over an `auto` height is silently
 * demoted to replacing it, and the panel then ignores the roll entirely.
 */
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
  const height = Math.min(natural - heightOf(section) + target, maxHeight(viewport));
  if (arrival) {
    // The summon is still landing, so this roll is part of the panel appearing rather than growth
    // after the fact: it ends centred on the height it is taking the panel to, and that is the edge
    // the session is then pinned to.
    memory.pinned = centred(viewport, height);
  }
  const bottom = clamped(memory.pinned, viewport, height);
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
  // Where this slide ends and when, in the same terms as the panel's own moves: a placement that
  // lands mid-ride and is going to the same place resumes this rather than restarting it. The
  // height is the prediction either way, since that is where the roll leaves the panel whether the
  // section drives it there or the carried ease does.
  memory.aim = { height, bottom };
  memory.lands = Date.now() + MORPH_ROLL_MS;
  memory.running = element.animate(
    carried === null
      ? [{ bottom: `${from}px` }, { bottom: `${bottom}px` }]
      : [frame(carried, from), frame(height, bottom)],
    { duration: MORPH_ROLL_MS, easing: EASING },
  );
}
