// Putting the panel where it belongs: the DOM adapter over `panelGeometry`'s arithmetic and
// `panelPin`'s rules. A CSS transition cannot do this, because the height is `auto` on both sides
// and only the content changed, which is not a change of computed value.

import { EASING, MORPHING_ATTRIBUTE } from "./morph";

/** Set on the panel while it is easing between two sizes. Read only by the stylesheet, which hides
 *  the history's scrollbar thumb for the duration. Written synchronously on every path out of
 *  `place`, never from an animation event, because `oncancel` arrives asynchronously. */
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

/** Put the panel where it belongs, and animate it there from wherever it was. The running
 *  animation is cancelled before measuring, because a height animation overrides the used height:
 *  read what is displayed, cancel, read the natural geometry, then animate between the two. */
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
    memory.arrived = Date.now();
  }
  memory.open = at.open;
  const viewport = window.innerHeight;
  // Read before the measuring cap below goes anywhere near the element. It is needed after a roll,
  // because the panel is already at the height the roll left it at, and measuring under the loose
  // cap instead would ease from a height the panel never had.
  const onScreen = heightOf(element);
  // Asked before the edge is decided, because deciding is also what forgets which view this was.
  const arrives = entering(memory, at);
  const release = holdScroll(element);
  // The cap depends on the bottom edge and the edge depends on the height, so both are decided in
  // one pass: measure under the loosest cap any edge could allow, work the edge out from that, and
  // apply the real cap afterwards. Whole pixels throughout, so the DOM and the arithmetic agree.
  capTo(element, openHeight(viewport));
  const section = element.querySelector<HTMLElement>(`[${MORPHING_ATTRIBUTE}]`);
  if (section !== null) {
    const rolling = Number(section.getAttribute(MORPHING_ATTRIBUTE));
    if (memory.rolling !== rolling) {
      memory.rolling = rolling;
      rideAlong(element, memory, section, viewport, arriving(memory, at));
    }
    // The roll owns the height but not the ceiling. The cap above is a measuring cap, and left
    // there for the length of the roll it lets the panel grow past the clear space at the top:
    // traced at 640x720, the panel rolled to 547 with its top edge off screen and snapped to 351.
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
  // Straight after a roll the height on screen is already the new one, because the panel followed
  // the roll to its end, and the bottom edge went along with it. `onScreen` rather than `height`,
  // because the two differ by whatever the measuring cap above just allowed.
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
  // A closing panel is not moved: it is about to be scaled away from where the eye last had it,
  // and the edge worked out above is for the summon that follows. A panel that has never been
  // placed is the exception, which is what makes the very first summon appear centred.
  const placed = at.open || memory.shown === null;
  // Used here and never folded into `memory.pinned`, so the edge the panel remembers stays the one
  // the chat is on, and a second placement in the same view cannot arrive twice.
  const edge = clamped(wanted);
  const arrival = arrives ? arrivalBottom(viewport, edge, height, tabSlack(element)) : edge;
  const bottom = placed ? arrival : memory.applied;
  const ceiling = maxHeight(viewport, bottom);
  capTo(element, ceiling);
  // Re-read, because the real cap may have shortened the panel, and everything below animates to
  // what the element actually is rather than to what it wanted to be.
  const next: Geometry = { height: heightOf(element), bottom };
  release();
  memory.applied = bottom;
  // Written with its fraction, because the keyframe below goes to this same edge and the element
  // holds it once the move is over. Rounded here instead, the two were half a pixel apart and the
  // panel's bordered edge stepped with nothing moving it.
  element.style.bottom = `${bottom}px`;
  memory.shown = next;
  // What the panel's own watch measures itself against from here: this placement answered the
  // content the panel has now, so the notification the ease is about to raise says nothing new.
  memory.placedFor = next.height;
  // Closed, arriving, first measurement, or nothing moved: keep the geometry and animate nothing.
  // Measuring while closed is what lets a reopen animate from a real height.
  if (!at.open || summoned || displayed === null || settled(displayed, next)) {
    element.removeAttribute(RESIZING_ATTRIBUTE);
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    element.removeAttribute(RESIZING_ATTRIBUTE);
    return;
  }
  // A render that did not redirect the panel resumes the move already in the air, over the time it
  // had left, rather than starting the clock again. A token arrives about every 55ms, and a fresh
  // ease per token pushed the arrival back by another floor's worth every time.
  const holding = live && settled(memory.aim, next);
  const duration = holding ? Math.max(memory.lands - Date.now(), 0) : durationOf(displayed, next);
  memory.aim = next;
  memory.lands = Date.now() + duration;
  const animation = element.animate(
    [
      // The ceiling the panel is going to is already on the element, and a panel easing down to it
      // started taller than that allows, so the move begins under a cap at the panel's own size.
      frame(displayed.height, displayed.bottom, Math.max(displayed.height, ceiling)),
      frame(next.height, next.bottom, ceiling),
    ],
    { duration, easing: EASING },
  );
  element.setAttribute(RESIZING_ATTRIBUTE, "");
  animation.onfinish = () => element.removeAttribute(RESIZING_ATTRIBUTE);
  memory.running = animation;
}
