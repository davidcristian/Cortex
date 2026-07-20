
import { EASING, MORPHING_ATTRIBUTE } from "./morph";

/** Set on the panel while it is easing between two sizes. */
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

/** Take the scroll positions the measurement below is about to cost, and give them back. */
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

/** Where the panel's bottom edge wants to be, before the ceiling has its say. */
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

/** Put the panel where it belongs, and animate it there from wherever it was. */
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
