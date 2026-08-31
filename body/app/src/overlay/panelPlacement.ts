// Putting the panel where it belongs: the DOM adapter over `panelGeometry`'s arithmetic and
// `panelPin`'s rules. It reads the element's box, decides the geometry the panel should have, writes
// the bottom edge, and plays the move. `usePanelMotion` is the React hook that drives it.
//
// Which edge the panel holds through all of that is `panelPin`, which is the half of this that is
// about the user's hand rather than about pixels, and reads as one piece written out together.
//
// Why this is code and not a CSS transition: a `transition: height` never fires here, because the
// panel's height is `auto` on both sides and only its *content* changed, which is not a computed
// value change. `interpolate-size: allow-keywords` does not help either; it makes `auto`
// interpolable against a length (`height: 0` to `height: auto`), rather than one content-driven
// `auto` against the next. Measured in a browser before this was written: with the transition
// declared and `interpolate-size` set, opening the switcher moved the panel through exactly one
// distinct height. So the old geometry is captured before paint and replayed as a real animation.

import { EASING, MORPHING_ATTRIBUTE } from "./morph";

/** Set on the panel while it is easing between two sizes. Read only by the stylesheet, which hides
 *  the history's scrollbar thumb for the duration: mid-ease the panel is shorter than the height it
 *  is easing to, so the history overflows for a few frames and flashes a thumb for a size the panel
 *  never settles at.
 *
 *  Written synchronously, on every path out of `place`, and never from an animation event. A
 *  cancelled animation dispatches `oncancel` asynchronously, so a handler that cleared the flag
 *  there ran after the replacement animation had already set it, and during a stream every token
 *  replaces the animation. Traced at 60Hz: 19 frames of a single reply had the history overflowing
 *  with the panel unmarked, which is the thumb the flag exists to hide. Only `onfinish` is left
 *  asynchronous, and it is safe: a replaced animation is cancelled, and a cancelled animation
 *  never finishes. */
const RESIZING_ATTRIBUTE = "data-resizing";
import { capTo } from "./panelBudget";
import {
  type Geometry,
  arrivalBottom,
  clamped,
  durationOf,
  frame,
  maxHeight,
  openHeight,
  settled,
} from "./panelGeometry";
import { type Memory, type Placement, arriving, heightOf, measure } from "./panelMemory";
import { centringHeight, holdScroll, tabSlack } from "./panelParts";
import { VIEW_CHANGE_RECENTRES, entering, pinnedBottom } from "./panelPin";
import { rideAlong } from "./panelRide";

/**
 * Put the panel where it belongs, and animate it there from wherever it was.
 *
 * The running animation is cancelled before measuring. A height animation overrides the used
 * height, so measuring while one runs returns the in-flight value rather than the natural one, and
 * reading it anyway costs the panel its content height: during a stream every token animates from
 * in-flight to in-flight, so the panel never converges and the text sits permanently clipped by the
 * panel's `overflow: hidden`. So the order is: read what is displayed, cancel, read the natural
 * geometry, animate between the two. That also keeps a change mid-ease continuous, because the new
 * animation starts exactly where the old one was.
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
  // apply the real cap. Sizing the cap from the previous edge instead lags a render, and the lag
  // shows: a summon centres for the height it has at that instant, then the reminder stack landing
  // a moment later grows upward from an edge chosen for a shorter panel. Measured at 900px, the
  // empty chat settled 82px below centre and scrolled, having capped itself at 520px where 604
  // would have fitted. Whole pixels throughout, so the numbers written to the DOM are the same ones
  // the arithmetic predicts against (`panelGeometry.maxHeight`).
  // What is on screen right now, read before the measuring cap goes anywhere near the element. It is
  // only needed after a roll, and it is needed then because the panel is already at the height the
  // roll left it at: measured under the loose cap instead, a panel sitting at its 450px ceiling with
  // the switcher open reads 547, and easing "from" 547 to 450 is a 97px jump to a top edge 11px off
  // the screen followed by a slide back down. That was the overshoot the roll's own cap was fixed to
  // stop, arriving one frame later by another route, and it was invisible before the ceiling learned
  // to ride along in the keyframes, because the cap on the element was clamping the ease flat.
  const onScreen = heightOf(element);
  // Asked before the edge is decided, because deciding is also what forgets which view the panel
  // was in: this is true only on the render that arrives in a multi-shape view.
  const arrives = entering(memory, at);
  const release = holdScroll(element);
  capTo(element, openHeight(viewport));
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
    // The roll owns the height, but not the ceiling. The cap above is a measuring cap, and a roll is
    // not a placement: left there for the length of the roll, it is the panel's licence to grow
    // clean past the clear space kept at the top. Traced at 60Hz at 640x720 with the panel near its
    // ceiling, opening the chat switcher: the panel rolled to the loose 547 with its top edge off
    // the screen, and the placement at the end of the roll put the real 351 back in one frame, which
    // is the overshoot and the pop back. Capped here instead, the section still rolls to its full
    // height and the history gives the room up, which is what the history is for.
    capTo(element, maxHeight(viewport, memory.applied));
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
  // Straight after a child-owned change, the height on screen is already the new one: the panel
  // followed the roll to its end, and the section holds its collapsed height until React removes
  // it. Remembering the mid-roll height instead and easing "from" there snapped the switcher back
  // open for one frame, which a trace caught before it was understood. The bottom edge rode along
  // with the roll, so as a rule there is nothing left here to move at all. The exception is a roll
  // the panel carried an interrupted ease through: there the panel drove its own height to a
  // predicted end, so the prediction is what is on screen, and anything that resized the panel while
  // the roll ran (a token landing mid-roll) is a residue to ease away rather than to snap.
  //
  // `onScreen` and not `height`: the two differ by whatever the measuring cap above just allowed,
  // which after a roll that ended at the ceiling is the whole overshoot (see the read itself).
  const displayed = deferred
    ? { height: carrying ?? onScreen, bottom: was }
    : (inFlight ?? memory.shown);
  const wanted = pinnedBottom(
    memory,
    at,
    viewport,
    centringHeight(element, height),
    height,
    recentres,
  );
  memory.pinned = wanted;
  // A closing panel is not moved. It is about to be scaled away from where the eye last had it, and
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
  // Spent here and never folded into `memory.pinned`, so the edge the panel remembers stays the
  // one the chat is standing on: the trip back is unaffected, and a second placement in the same
  // view cannot arrive twice. Every later resize inside the view holds the top this set (rule 4).
  const edge = clamped(wanted);
  const arrival = arrives ? arrivalBottom(viewport, edge, height, tabSlack(element)) : edge;
  const bottom = placed ? arrival : memory.applied;
  const ceiling = maxHeight(viewport, bottom);
  capTo(element, ceiling);
  // Re-read: the real cap may have shortened the panel, and everything below animates to what the
  // element actually is rather than to what it wanted to be. It may also have shortened the
  // roll-open sections, the budget they share being a share of this same number, and the re-read
  // covers that for the same reason: the panel animates to what the element actually is.
  const next: Geometry = { height: heightOf(element), bottom };
  release();
  memory.applied = bottom;
  // Written with its fraction, because the keyframe below goes to this same edge and the element
  // holds it once the move is over. Rounded here instead, the two were different numbers: measured
  // at 901x1001, one growth's whole ease painted a 324.5px edge and the frame that took the
  // animation away handed back the 325px inline value, which is half a pixel of the panel's
  // bordered, shadowed edge stepping with nothing moving it. The ceiling is still whole
  // (`panelGeometry.maxHeight` rounds its own answer), so the number that is reasoned about after
  // being written is unaffected.
  element.style.bottom = `${bottom}px`;
  memory.shown = next;
  // What the panel's own watch measures itself against from here: this placement answered the
  // content the panel has now, so the notification the ease below is about to raise has nothing
  // behind it.
  memory.placedFor = next.height;
  if (!at.open || summoned || displayed === null || settled(displayed, next)) {
    // Closed, arriving, first measurement, or nothing moved: keep the geometry for next time,
    // animate nothing. Measuring while closed is what lets a reopen animate from a real height.
    // The summon is on that list because the panel is not travelling to where it is opening: the
    // pop owns that arrival, and with the close no longer re-centring, the geometry it arrives at
    // is genuinely new rather than the one the dismiss left ready.
    element.removeAttribute(RESIZING_ATTRIBUTE);
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    element.removeAttribute(RESIZING_ATTRIBUTE);
    return;
  }
  // A render that did not redirect the panel resumes the move already in the air, over the time it
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
      // The ceiling the panel is going to is already on the element, and a panel easing down to it
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
