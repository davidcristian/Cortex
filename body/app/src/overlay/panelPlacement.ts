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

/** Every box inside the panel that scrolls: the conversation, and a console tab's rows. Written out
 *  rather than discovered, because discovering it means reading `scrollTop` off every node in the
 *  panel on every token of a stream. A new scrolling box in the panel belongs in this list. */
const SCROLL_BOXES = ".history, .rows";

/**
 * Take the scroll positions the measurement below is about to cost, and give them back.
 *
 * The panel measures itself by growing to the loosest cap any edge could allow and reading what it
 * becomes (`openHeight`). A scroll box inside a taller panel is a taller box, and the engine answers
 * a box that has outgrown its own scroll range by CLAMPING it to the range it now has, which putting
 * the real cap back does not undo. So the panel's own measurement walks the log up under the reader.
 *
 * Traced at 60Hz at 640x720 through a streamed reply, wheeling 60px up from the tail: `scrollTop`
 * read 312, then 252 the frame the wheel landed, then 215 two frames later with nothing else
 * touching it, 215 being exactly the deepest a 390px window can scroll a 605px log. Every token did
 * it again, which is what "the history will not let me scroll while a reply streams" is. The same
 * clamp lands on the way back from the console, where it took the position `ChatView` had just
 * restored and left the log 97px off the tail rather than where the reader was.
 */
function holdScroll(element: HTMLElement): () => void {
  const boxes = [...element.querySelectorAll<HTMLElement>(SCROLL_BOXES)].map(
    (box) => [box, box.scrollTop] as const,
  );
  return () => {
    for (const [box, top] of boxes) {
      box.scrollTop = top;
    }
  };
}

/**
 * Where the panel's bottom edge wants to be, before the ceiling has its say.
 *
 * Also updates the memory the next such decision reads: which view is on screen, and where the chat
 * was parked when it was left. A closed panel always re-centres, because it is about to be summoned
 * and should come back to the middle rather than to wherever the last conversation had pushed it.
 */
/** The height the panel centres ON, which is not always the height it HAS. A section marked `aside`
 *  is left out of it: the reminder stack arrives with the summon and can be two rows or five, so
 *  centring on it puts the conversation wherever the day's reminders happen to leave it. The chat
 *  centres on itself and the stack grows it upward from there, the way every other arrival does.
 *
 *  Only an aside in the view being PLACED counts. The view being left is still in the DOM for one
 *  morph, and a stack belonging to it was being subtracted from the height of the view arriving,
 *  which has no stack and never did. Measured at 640x720 entering the console over an empty chat
 *  with three reminders up: the console is 347px tall and was centred as though it were 155, which
 *  put it 96px above the middle of the screen and, since the ceiling is measured from the edge it
 *  sits on, capped it at 351px instead of 448. The console then had four spare pixels in it, and
 *  anything added to a tab scrolled rather than fitting. */
function centringHeight(element: HTMLElement, height: number): number {
  const aside = element.querySelector<HTMLElement>(".view:not(.out) .collapse.aside");
  return height - (aside?.offsetHeight ?? 0);
}

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
  const displayed = deferred
    ? { height: carrying ?? height, bottom: was }
    : (inFlight ?? memory.shown);
  const wanted = wantedBottom(memory, at, viewport, centringHeight(element, height));
  memory.pinned = wanted;
  const bottom = clamped(wanted);
  const ceiling = maxHeight(viewport, bottom);
  element.style.maxHeight = `${ceiling}px`;
  // Re-read: the real cap may have shortened the panel, and everything below animates to what the
  // element actually is rather than to what it wanted to be.
  const next: Geometry = { height: heightOf(element), bottom };
  release();
  memory.applied = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  memory.shown = next;
  if (!at.open || displayed === null || settled(displayed, next)) {
    // Closed, first measurement, or nothing moved: keep the geometry for next time, animate
    // nothing. Measuring while closed is what lets a reopen animate from a real height.
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
