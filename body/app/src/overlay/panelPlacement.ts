// Putting the panel where it belongs: the DOM adapter over `panelGeometry`'s arithmetic. It reads
// the element's box, decides the geometry the panel should have, writes the bottom edge, and plays
// the move. `usePanelMotion` is the React hook that drives it.
//
// Three rules share one measurement:
//
//   1. ENTERING ANOTHER VIEW centres it. Opening the console, or moving between its tabs, resizes
//      the panel to what that view needs and slides it into the true middle of the screen.
//   2. COMING BACK TO THE CHAT restores it. The chat's own bottom edge is parked on the way out and
//      handed back on the way in, so a trip to the console and back leaves the conversation exactly
//      where the eye left it. Re-centring the return trip too was wrong twice over: the chat
//      arrived somewhere it had never been, and the move had no meaning, since nothing about the
//      chat had changed while it was away.
//   3. GROWTH INSIDE A VIEW pushes the top edge up. A reply arriving, the switcher list opening, a
//      new chat emptying the panel, the composer taking a second line: the bottom stays pinned
//      where it was, so the composer never slides out from under the hand that just typed into it.
//      Minting a new chat belongs here and not in rule 1: it is the same view with less in it.
//
// A summon is outside all three: for as long as the panel is arriving it centres on whatever it
// currently is, so content that lands behind the summon (the reminder pull, a restored
// conversation) is the panel appearing with it rather than growth from an edge it was pinned to
// before it had any.
//
// Why this is code and not a CSS transition: a `transition: height` never fires here, because the
// panel's height is `auto` on both sides and only its *content* changed, which is not a computed
// value change. `interpolate-size: allow-keywords` does not help either; it makes `auto`
// interpolable against a LENGTH (`height: 0` to `height: auto`), not one content-driven `auto`
// against the next. Measured in a browser before this was written: with the transition declared
// and `interpolate-size` set, opening the switcher moved the panel through exactly one distinct
// height. So the old geometry is captured before paint and replayed as a real animation.

import { EASING, MORPHING_ATTRIBUTE } from "./morph";

/** Set on the panel while it is easing between two sizes. Read only by the stylesheet, which hides
 *  the history's scrollbar thumb for the duration: mid-ease the panel is shorter than the height it
 *  is easing to, so the history overflows for a few frames and flashes a thumb for a size the panel
 *  never settles at. */
const RESIZING_ATTRIBUTE = "data-resizing";
import {
  type Geometry,
  centred,
  clamped,
  durationOf,
  frame,
  maxHeight,
  openHeight,
  settled,
} from "./panelGeometry";
import { type Memory, type Placement, arriving, heightOf, measure } from "./panelMemory";
import { rideAlong } from "./panelRide";

/** The view whose position is remembered across a trip to another one. */
const CHAT_VIEW = "chat";

/**
 * Where the panel's bottom edge wants to be, before the ceiling has its say.
 *
 * Also updates the memory the next such decision reads: which view is on screen, and where the chat
 * was parked when it was left. A closed panel always re-centres, because it is about to be summoned
 * and should come back to the middle rather than to wherever the last conversation had pushed it.
 */
function wantedBottom(memory: Memory, at: Placement, viewport: number, height: number): number {
  const changed = memory.view !== at.view;
  if (changed && memory.view === CHAT_VIEW) {
    memory.parked = memory.pinned;
  }
  memory.view = at.view;
  const parked = changed && at.view === CHAT_VIEW ? memory.parked : null;
  const centre =
    !at.open ||
    memory.shown === null ||
    at.recentre ||
    arriving(memory, at) ||
    (changed && parked === null);
  return centre ? centred(viewport, height) : (parked ?? memory.pinned);
}

/**
 * Put the panel where it belongs, and animate it there from wherever it was.
 *
 * **The running animation is cancelled before measuring.** A height animation overrides the used
 * height, so measuring while one runs returns the in-flight value, not the natural one. Reading it
 * anyway is the bug this note exists to prevent: during a stream every token would animate from
 * in-flight to in-flight, the panel would never converge on its content height, and the text would
 * sit permanently clipped by the panel's `overflow: hidden`. So the order is: read what is
 * displayed, cancel, read the natural geometry, animate between the two. That also keeps a change
 * mid-ease continuous, because the new animation starts exactly where the old one was.
 */
export function place(element: HTMLElement | null, memory: Memory, at: Placement): void {
  if (element === null) {
    return;
  }
  if (at.open && !memory.open) {
    // A summon: the panel is arriving, and owns its own geometry for as long as that takes.
    memory.arrived = Date.now();
  }
  memory.open = at.open;
  const viewport = window.innerHeight;
  // The cap depends on the bottom edge and the edge depends on the height, so both are decided in
  // one pass: measure under the loosest cap any edge could allow, work the edge out from that, then
  // apply the real cap. Sizing the cap from the PREVIOUS edge instead lags a render, and the lag
  // shows: a summon centres for the height it has at that instant, then the reminder stack landing
  // a moment later grows upward from an edge chosen for a shorter panel. Measured at 900px, the
  // empty chat settled 82px below centre and scrolled, having capped itself at 520px where 604
  // would have fitted. Whole pixels throughout, so the numbers written to the DOM are the same ones
  // the arithmetic predicts against (`panelGeometry.maxHeight`).
  element.style.maxHeight = `${openHeight(viewport)}px`;
  const section = element.querySelector<HTMLElement>(`[${MORPHING_ATTRIBUTE}]`);
  if (section !== null) {
    // A section inside is collapsing open or shut, and it owns the height: the panel's `auto` height
    // follows the section's animated one frame by frame, which is what makes the two read as a
    // single movement. All the panel does is take its bottom edge along, once per roll.
    const rolling = Number(section.getAttribute(MORPHING_ATTRIBUTE));
    if (memory.rolling !== rolling) {
      memory.rolling = rolling;
      rideAlong(element, memory, section, viewport, arriving(memory, at));
    }
    // Record what the eye sees, so a later change eases from here.
    memory.shown = { height: heightOf(element), bottom: memory.applied };
    memory.deferred = true;
    return;
  }
  memory.rolling = null;
  const deferred = memory.deferred;
  memory.deferred = false;
  const carrying = memory.carrying;
  memory.carrying = null;
  const was = memory.applied;
  const live = memory.running !== null && memory.running.playState === "running";
  const inFlight = live ? measure(element, viewport) : null;
  memory.running?.cancel();
  memory.running = null;
  const height = heightOf(element);
  // Straight after a child-owned change, the height on screen is ALREADY the new one: the panel
  // followed the roll to its end, and the section holds its collapsed height until React removes
  // it. Remembering the mid-roll height instead and easing "from" there snapped the switcher back
  // open for one frame, which a trace caught before it was understood. The bottom edge rode along
  // with the roll, so as a rule there is nothing left here to move at all. The exception is a roll
  // the panel carried an interrupted ease through: there the panel drove its own height to a
  // PREDICTED end, so the prediction is what is on screen, and anything that resized the panel while
  // the roll ran (a token landing mid-roll) is a residue to ease away rather than to snap.
  const displayed = deferred
    ? { height: carrying ?? height, bottom: was }
    : (inFlight ?? memory.shown);
  const wanted = wantedBottom(memory, at, viewport, height);
  memory.pinned = wanted;
  const bottom = clamped(wanted);
  element.style.maxHeight = `${maxHeight(viewport, bottom)}px`;
  // Re-read: the real cap may have shortened the panel, and everything below animates to what the
  // element actually is rather than to what it wanted to be.
  const next: Geometry = { height: heightOf(element), bottom };
  memory.applied = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  memory.shown = next;
  if (!at.open || displayed === null || settled(displayed, next)) {
    // Closed, first measurement, or nothing moved: keep the geometry for next time, animate
    // nothing. Measuring while closed is what lets a reopen animate from a real height.
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  // A render that did not redirect the panel RESUMES the move already in the air, over the time it
  // had left, rather than starting the clock again. That is the difference between converging on a
  // streamed reply and chasing it: a token lands about every 55ms, each one re-renders the panel,
  // and a fresh ease per token pushed the landing back by another floor's worth every time.
  // Measured over one reply before this: a 23px line of growth started four eases (120ms each,
  // 55ms apart) and took 285ms to settle. It now lands 120ms after the line appeared, whatever the
  // tokens do meanwhile, because every render after the first only shortens the same move.
  const holding = live && settled(memory.aim, next);
  const duration = holding ? Math.max(memory.lands - Date.now(), 0) : durationOf(displayed, next);
  memory.aim = next;
  memory.lands = Date.now() + duration;
  const animation = element.animate(
    [frame(displayed.height, displayed.bottom), frame(next.height, next.bottom)],
    { duration, easing: EASING },
  );
  element.setAttribute(RESIZING_ATTRIBUTE, "");
  // Both endings clear it. A cancel is the common one during a stream, where the next token's
  // render replaces this move, and that render sets the attribute again on its way out.
  animation.onfinish = () => element.removeAttribute(RESIZING_ATTRIBUTE);
  animation.oncancel = animation.onfinish;
  memory.running = animation;
}
