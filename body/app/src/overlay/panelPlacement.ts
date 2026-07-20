
import { EASING, MORPHING_ATTRIBUTE } from "./morph";
import {
  type Geometry,
  centred,
  clamped,
  durationOf,
  frame,
  maxHeight,
  settled,
} from "./panelGeometry";
import { type Memory, type Placement, arriving, heightOf, measure } from "./panelMemory";
import { rideAlong } from "./panelRide";

/** The view whose position is remembered across a trip to another one. */
const CHAT_VIEW = "chat";

/** Where the panel's bottom edge wants to be, before the ceiling has its say. */
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
  // No rounding here: the ceiling arrives in whole pixels so that what the element is given and what
  // the arithmetic predicts against cannot disagree (`panelGeometry.maxHeight`).
  element.style.maxHeight = `${maxHeight(viewport)}px`;
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
  const displayed = deferred
    ? { height: carrying ?? height, bottom: was }
    : (inFlight ?? memory.shown);
  const wanted = wantedBottom(memory, at, viewport, height);
  memory.pinned = wanted;
  const next: Geometry = { height, bottom: clamped(wanted, viewport, height) };
  memory.applied = next.bottom;
  element.style.bottom = `${Math.round(next.bottom)}px`;
  memory.shown = next;
  if (!at.open || displayed === null || settled(displayed, next)) {
    // Closed, first measurement, or nothing moved: keep the geometry for next time, animate
    // nothing. Measuring while closed is what lets a reopen animate from a real height.
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  const holding = live && settled(memory.aim, next);
  const duration = holding ? Math.max(memory.lands - Date.now(), 0) : durationOf(displayed, next);
  memory.aim = next;
  memory.lands = Date.now() + duration;
  memory.running = element.animate(
    [frame(displayed.height, displayed.bottom), frame(next.height, next.bottom)],
    { duration, easing: EASING },
  );
}
