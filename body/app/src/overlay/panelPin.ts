// Which edge the panel holds, in four rules over one measurement: entering another view resizes
// it in place, returning to the chat restores where the chat was, growth inside the chat pushes
// its top edge up, and a resize in any other view pushes the bottom edge down.

import { centred } from "./panelGeometry";
import { type Memory, type Placement, arriving } from "./panelMemory";

/** The view whose position is remembered across a trip to another one. */
const CHAT_VIEW = "chat";

/** Whether entering another view slides the panel to the true middle of the screen, or keeps the
 *  bottom edge it is on and resizes in place. `place` takes it as a defaulted argument, so the
 *  tests cover both branches, and changing this constant is the whole change back. */
export const VIEW_CHANGE_RECENTRES = false;

/** Whether the panel is arriving in a view with more than one shape, which is the one render that
 *  hangs it from the top its tallest shape would take. Asked before `pinnedBottom` decides
 *  anything, because deciding is also what forgets which view the panel was in. */
export function entering(memory: Memory, at: Placement): boolean {
  return at.open && memory.view !== at.view && at.view !== CHAT_VIEW;
}

/** Where the panel's bottom edge wants to be, before the ceiling has its say. It also updates the
 *  memory the next such decision reads: which view is on screen, and where the chat was left. A
 *  closed panel always re-centres, because it is about to be summoned. */
export function pinnedBottom(
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
  // A resize inside a view other than the chat holds that view's top edge, so the growth happens
  // at the bottom. Which edge holds depends on where the hand is: a console tab is changed from
  // the strip at the top, and the chat's composer is at the other end.
  if (!changed && at.view !== CHAT_VIEW) {
    return shown.bottom + shown.height - height;
  }
  return memory.pinned;
}
