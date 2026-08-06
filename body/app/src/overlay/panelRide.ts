// The slide the panel makes alongside a section rolling open or shut inside it. The section owns
// the height while it rolls (`morph.ts`); this is the only thing the panel does about it.

import { EASING, MIN_DELTA_PX, MORPHING_ATTRIBUTE, MORPH_ROLL_MS } from "./morph";
import { centred, clamped, frame, maxHeight, openHeight } from "./panelGeometry";
import { type Memory, heightOf, measure } from "./panelMemory";
import { centringHeight } from "./panelParts";

/**
 * Slide the bottom edge to where the roll now running will leave it, over that same roll.
 *
 * A section rolling open can push the panel past the ceiling, and the panel is anchored by its
 * bottom edge, so the growth has only the top edge to go to and it stops there: the prediction
 * below is capped at the ceiling and the history gives the room up. It used to grow DOWNWARD
 * instead, walking the composer back down the screen, and that second bound was deleted 2026-07-20;
 * this sentence went on describing it until 2026-08-06. Sliding only once the roll
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
  const raw = natural - heightOf(section) + target;
  if (arrival) {
    // The summon is still landing, so this roll is part of the panel appearing rather than growth
    // after the fact: it ends centred on the height it is taking the panel to, and that is the edge
    // the session is then pinned to.
    //
    // Counted through `centringHeight`, the SAME function the placement at the end of the roll
    // counts its own measurement with, which is what makes this edge a measurement rather than a
    // guess at one. The section's current height cancels out of `raw`, so the prediction is exact,
    // and asking the two questions the same way is what makes the placement afterwards find
    // nothing left to move. Written out here instead, it asked only whether the ROLLING section was
    // the aside, so an aside merely STANDING in the panel was counted into the centring by the
    // ride-along and out of it by the placement: measured at 900x1000 over the demo, Ctrl+N with
    // the switcher list open (the list rolls shut behind the summon while the reminder stack
    // stands) pinned the panel to 227 where the placement at the end of the roll re-centred it to
    // 324, and a touch inside the arrival window, which is what stops that placement re-centring,
    // left the session 97px low for the rest of it.
    //
    // Bounded at `openHeight`, the loose cap the placement measures the panel under, and bounded
    // BEFORE the aside comes off for the same reason: that is the order the measurement happens in,
    // the element having already been capped when its height is read. Bounding it after put the
    // ride-along a whole aside above the placement on any panel whose content outgrows that cap.
    // Bounding it at the OLD edge's ceiling, tighter still, was worse than either: it centred the
    // chat on a remainder, pinned an edge the whole panel could not fit above, and let the cap
    // written for that edge squeeze the chat under the rolling stack until the placement after the
    // roll undid it, which at 760px with the demo's reminders cost the history 119px over the roll
    // and gave 40 back in a second ease.
    memory.pinned = centred(viewport, centringHeight(element, Math.min(raw, openHeight(viewport))));
  }
  const bottom = clamped(memory.pinned);
  const ceiling = maxHeight(viewport, bottom);
  // The height this roll leaves the panel at, under the ceiling of the edge it now stands on: a
  // prediction the panel cannot reach places it for a height it will never have (see the trace
  // in the doc comment above). Outside an arrival the pinned edge is the applied one, so this is
  // the same cap it always was.
  const height = Math.min(raw, ceiling);
  const from = shown?.bottom ?? memory.applied;
  // Only a HEIGHT ease has to be carried. The other thing that can be in the air here is a slide of
  // the bottom edge alone (an earlier ride-along), which leaves the height to the section anyway.
  //
  // An ARRIVAL whose section outgrows the ceiling is the third case, and it carries the height
  // on purpose rather than because something was interrupted. Left to `auto`, the panel follows
  // the roll one-for-one until the cap bites, and the section's remaining growth then squeezes
  // the chat under it: two phases inside one roll, the empty state holding its size and
  // resizing only in the tail, which the maintainer caught on the summon. Driven from here to the
  // predicted height over the roll's own clock and curve, the chat's window compresses in step
  // with the stack growing, and everything arrives at the size it keeps.
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
  // Where this slide ends and when, in the same terms as the panel's own moves: a placement that
  // lands mid-ride and is going to the same place resumes this rather than restarting it. The
  // height is the prediction either way, since that is where the roll leaves the panel whether the
  // section drives it there or the carried ease does.
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
