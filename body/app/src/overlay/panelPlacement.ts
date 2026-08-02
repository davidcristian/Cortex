// Putting the panel where it belongs: the DOM adapter over `panelGeometry`'s arithmetic. It reads
// the element's box, decides the geometry the panel should have, writes the bottom edge, and plays
// the move. `usePanelMotion` is the React hook that drives it.
//
// Three rules share one measurement:
//
//   1. ENTERING ANOTHER VIEW resizes it in place. Opening the console, or moving between its tabs,
//      resizes the panel to what that view needs from the bottom edge the chat is standing on, the
//      way growth inside a view does. It shipped sliding to the true middle of the screen instead,
//      and the user, having lived with it, chose the standing edge (2026-07-21); the slide stays
//      one flip away behind `VIEW_CHANGE_RECENTRES`, both settings under test.
//   2. COMING BACK TO THE CHAT restores it. The chat's own bottom edge is parked on the way out and
//      handed back on the way in, so a trip to the console and back leaves the conversation exactly
//      where the eye left it. With rule 1 holding the edge anyway, the park is a no-op today; it is
//      kept because it is what makes the return correct the moment the slide is switched back on.
//   3. GROWTH INSIDE THE CHAT pushes the top edge up. A reply arriving, the switcher list opening,
//      a new chat emptying the panel, the composer taking a second line: the bottom stays pinned
//      where it was, so the composer never slides out from under the hand that just typed into it.
//      Minting a new chat belongs here and not in rule 1: it is the same view with less in it.
//   4. A RESIZE INSIDE ANY OTHER VIEW pushes the bottom edge down instead, holding the top. Which
//      edge holds is decided by where the hand is, and the console's chrome is its tab strip, at
//      the top: changing tabs must not slide the strip out from under the cursor that clicked it.
//      Rule 3 is the same principle at the chat's other end. A view with more than one shape is
//      entered at the top its TALLEST shape would take (`tabSlack`), so that held top is the same
//      one whichever tab the console is opened on, and a shorter tab ends higher rather than
//      starting lower.
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
 *  never settles at.
 *
 *  Written SYNCHRONOUSLY, on every path out of `place`, and never from an animation event. A
 *  cancelled animation dispatches `oncancel` asynchronously, so a handler that cleared the flag
 *  there ran AFTER the replacement animation had already set it, and during a stream every token
 *  replaces the animation. Traced at 60Hz: 19 frames of a single reply had the history overflowing
 *  with the panel unmarked, which is the thumb the flag exists to hide. Only `onfinish` is left
 *  asynchronous, and it is safe: a replaced animation is cancelled, and a cancelled animation
 *  never finishes. */
const RESIZING_ATTRIBUTE = "data-resizing";
import {
  type Geometry,
  arrivalBottom,
  centred,
  clamped,
  durationOf,
  frame,
  maxHeight,
  openHeight,
  settled,
} from "./panelGeometry";
import { type Memory, type Placement, arriving, heightOf, measure } from "./panelMemory";
import { centringHeight, holdScroll, tabSlack } from "./panelParts";
import { rideAlong } from "./panelRide";

/** The view whose position is remembered across a trip to another one. */
const CHAT_VIEW = "chat";

/** Whether entering another view slides the panel to the true middle of the screen, or keeps the
 *  bottom edge it is standing on and resizes in place. The slide shipped first; the maintainer chose
 *  the standing edge after living with both (2026-07-21), and asked for the slide to stay a
 *  switch rather than a memory. `place` takes it as a defaulted argument so the tests hold both
 *  branches green, and flipping this constant is the whole change back. */
export const VIEW_CHANGE_RECENTRES = false;

/**
 * Where the panel's bottom edge wants to be, before the ceiling has its say.
 *
 * Also updates the memory the next such decision reads: which view is on screen, and where the chat
 * was parked when it was left. A closed panel always re-centres, because it is about to be summoned
 * and should come back to the middle rather than to wherever the last conversation had pushed it.
 */
function wantedBottom(
  memory: Memory,
  at: Placement,
  viewport: number,
  centring: number,
  height: number,
  recentres: boolean,
): number {
  const changed = memory.view !== at.view;
  if (changed && memory.view === CHAT_VIEW) {
    memory.parked = memory.pinned;
  }
  memory.view = at.view;
  const shown = memory.shown;
  // Nothing on screen to hold on to yet: a first placement centres, whatever else is true.
  if (shown === null) {
    return centred(viewport, centring);
  }
  const parked = changed && at.view === CHAT_VIEW ? memory.parked : null;
  if (!at.open || at.recentre || arriving(memory, at) || (recentres && changed && parked === null)) {
    return centred(viewport, centring);
  }
  if (parked !== null) {
    return parked;
  }
  // A resize INSIDE a view other than the chat holds that view's TOP edge, so the growth happens
  // at the bottom. Which edge holds is decided by where the hand is: a console tab is changed
  // from the strip at the top, and that strip must not move out from under the cursor that just
  // clicked it. The chat is the other way round for the same reason, its composer being the edge
  // the hand is on, which is why rule 3 above pins its bottom. Entering a view is neither, and
  // keeps the edge it arrived on (rule 1): the opener that was clicked is down in the hint strip.
  if (!changed && at.view !== CHAT_VIEW) {
    return shown.bottom + shown.height - height;
  }
  return memory.pinned;
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
export function place(
  element: HTMLElement | null,
  memory: Memory,
  at: Placement,
  recentres = VIEW_CHANGE_RECENTRES,
): void {
  if (element === null) {
    return;
  }
  const summoned = at.open && !memory.open;
  if (summoned) {
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
  // What the eye has RIGHT NOW, read before the measuring cap goes anywhere near the element. It is
  // only needed after a roll, and it is needed then because the panel is already at the height the
  // roll left it at: measured under the loose cap instead, a panel sitting at its 450px ceiling with
  // the switcher open reads 547, and easing "from" 547 to 450 is a 97px jump to a top edge 11px off
  // the screen followed by a slide back down. That was the overshoot the roll's own cap was fixed to
  // stop, arriving one frame later by another route, and it was invisible before the ceiling learned
  // to ride along in the keyframes, because the cap on the element was clamping the ease flat.
  const onScreen = heightOf(element);
  // Asked before `wantedBottom` decides anything, because deciding is also what forgets which view
  // the panel was in: this is true only on the render that ARRIVES in a multi-shape view.
  const entering = at.open && memory.view !== at.view && at.view !== CHAT_VIEW;
  const release = holdScroll(element);
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
    // The roll owns the height, but not the ceiling. The cap above is a MEASURING cap, and a roll is
    // not a placement: left there for the length of the roll, it is the panel's licence to grow
    // clean past the clear space kept at the top. Traced at 60Hz at 640x720 with the panel near its
    // ceiling, opening the chat switcher: the panel rolled to the loose 547 with its top edge off
    // the screen, and the placement at the END of the roll put the real 351 back in one frame, which
    // is the overshoot and the pop back. Capped here instead, the section still rolls to its full
    // height and the history gives the room up, which is what the history is for.
    element.style.maxHeight = `${maxHeight(viewport, memory.applied)}px`;
    // Record what the eye sees, so a later change eases from here.
    memory.shown = { height: heightOf(element), bottom: memory.applied };
    memory.deferred = true;
    release();
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
  //
  // `onScreen` and not `height`: the two differ by whatever the measuring cap above just allowed,
  // which after a roll that ended at the ceiling is the whole overshoot (see the read itself).
  const displayed = deferred
    ? { height: carrying ?? onScreen, bottom: was }
    : (inFlight ?? memory.shown);
  const wanted = wantedBottom(
    memory,
    at,
    viewport,
    centringHeight(element, height),
    height,
    recentres,
  );
  memory.pinned = wanted;
  // A CLOSING PANEL IS NOT MOVED. It is about to be scaled away from where the eye last had it, and
  // the edge worked out above is for the summon that follows, which centres for itself anyway
  // (`arriving` covers the whole of that arrival). Written while it closes instead, it lands in the
  // frame of the dismiss, with the panel still at full size and fully opaque: traced at 60Hz at
  // 640x720 with a conversation and the session list up, the panel went from 450 tall at a 184px
  // edge to 508 tall at a 106px edge in one frame, and only then began to shrink away. A dismiss is
  // not a placement, and the panel keeps the geometry it is standing in for the length of it.
  //
  // A panel that has never been placed is the exception, and it is why this is not simply `at.open`:
  // there is no geometry to keep, so it takes the one it would open at, which is what makes the very
  // first summon appear centred rather than sliding there.
  const placed = at.open || memory.shown === null;
  // Spent HERE and never folded into `memory.pinned`, so the edge the panel remembers stays the
  // one the chat is standing on: the trip back is unaffected, and a second placement in the same
  // view cannot arrive twice. Every later resize inside the view holds the top this set (rule 4).
  const edge = clamped(wanted);
  const arrival = entering ? arrivalBottom(viewport, edge, height, tabSlack(element)) : edge;
  const bottom = placed ? arrival : memory.applied;
  const ceiling = maxHeight(viewport, bottom);
  element.style.maxHeight = `${ceiling}px`;
  // Re-read: the real cap may have shortened the panel, and everything below animates to what the
  // element actually is rather than to what it wanted to be.
  const next: Geometry = { height: heightOf(element), bottom };
  release();
  memory.applied = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  memory.shown = next;
  if (!at.open || summoned || displayed === null || settled(displayed, next)) {
    // Closed, arriving, first measurement, or nothing moved: keep the geometry for next time,
    // animate nothing. Measuring while closed is what lets a reopen animate from a real height.
    // The SUMMON is on that list because the panel is not travelling to where it is opening: the
    // pop owns that arrival, and with the close no longer re-centring, the geometry it arrives at
    // is genuinely new rather than the one the dismiss left ready.
    element.removeAttribute(RESIZING_ATTRIBUTE);
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    element.removeAttribute(RESIZING_ATTRIBUTE);
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
    [
      // The ceiling the panel is going to is already on the element, and a panel easing DOWN to it
      // started taller than it allows, so the move begins under a cap that starts where the panel
      // actually is (`frame` has the trace).
      frame(displayed.height, displayed.bottom, Math.max(displayed.height, ceiling)),
      frame(next.height, next.bottom, ceiling),
    ],
    { duration, easing: EASING },
  );
  element.setAttribute(RESIZING_ATTRIBUTE, "");
  animation.onfinish = () => element.removeAttribute(RESIZING_ATTRIBUTE);
  memory.running = animation;
}
