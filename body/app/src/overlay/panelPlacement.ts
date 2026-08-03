
import { EASING, MORPHING_ATTRIBUTE } from "./morph";

/** Set on the panel while it is easing between two sizes. */
const RESIZING_ATTRIBUTE = "data-resizing";
import { capTo } from "./panelBudget";
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

/**
 * Whether entering another view slides the panel to the true middle of the screen, or keeps the
 * bottom edge it is standing on and resizes in place.
 */
export const VIEW_CHANGE_RECENTRES = false;

/** Where the panel's bottom edge wants to be, before the ceiling has its say. */
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
  if (!changed && at.view !== CHAT_VIEW) {
    return shown.bottom + shown.height - height;
  }
  return memory.pinned;
}

/** Put the panel where it belongs, and animate it there from wherever it was. */
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
  const onScreen = heightOf(element);
  // Asked before `wantedBottom` decides anything, because deciding is also what forgets which view
  // the panel was in: this is true only on the render that ARRIVES in a multi-shape view.
  const entering = at.open && memory.view !== at.view && at.view !== CHAT_VIEW;
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
  const placed = at.open || memory.shown === null;
  // Spent HERE and never folded into `memory.pinned`, so the edge the panel remembers stays the
  // one the chat is standing on: the trip back is unaffected, and a second placement in the same
  // view cannot arrive twice. Every later resize inside the view holds the top this set (rule 4).
  const edge = clamped(wanted);
  const arrival = entering ? arrivalBottom(viewport, edge, height, tabSlack(element)) : edge;
  const bottom = placed ? arrival : memory.applied;
  const ceiling = maxHeight(viewport, bottom);
  capTo(element, ceiling);
  const next: Geometry = { height: heightOf(element), bottom };
  release();
  memory.applied = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  memory.shown = next;
  if (!at.open || summoned || displayed === null || settled(displayed, next)) {
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
